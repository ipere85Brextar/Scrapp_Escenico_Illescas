"""
Script para GitHub Actions: ejecuta un check unico de todas las URLs.
Usa un Gist de GitHub como almacenamiento de estado persistente.
"""

import json
import os
import sys

sys.path.insert(0, "src")

import httpx

from config import TARGET_URLS
from scraper import fetch_page, extract_title, ScraperError
from detector import analyze
from notifier import send_alert

GIST_ID = os.environ.get("STATE_GIST_ID", "")
GITHUB_TOKEN = os.environ.get("GH_TOKEN", "")
STATE_FILE = "scrapp_state.json"


def load_state() -> dict:
    """Carga estado desde GitHub Gist o retorna estado vacio."""
    if GIST_ID and GITHUB_TOKEN:
        try:
            resp = httpx.get(
                f"https://api.github.com/gists/{GIST_ID}",
                headers={"Authorization": f"token {GITHUB_TOKEN}"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["files"][STATE_FILE]["content"]
                return json.loads(content)
        except Exception as e:
            print(f"Warning: no se pudo cargar estado del Gist: {e}")
    return {}


def save_state(state: dict):
    """Guarda estado en GitHub Gist."""
    if not GIST_ID or not GITHUB_TOKEN:
        print("Warning: no se puede guardar estado (sin GIST_ID o GH_TOKEN)")
        return

    try:
        httpx.patch(
            f"https://api.github.com/gists/{GIST_ID}",
            headers={"Authorization": f"token {GITHUB_TOKEN}"},
            json={"files": {STATE_FILE: {"content": json.dumps(state, indent=2)}}},
            timeout=10,
        )
    except Exception as e:
        print(f"Warning: no se pudo guardar estado en Gist: {e}")


def main():
    state = load_state()
    check_count = state.get("total_checks", 0) + 1
    print(f"Check #{check_count}")

    any_error = False

    for url in TARGET_URLS:
        url_key = url.rstrip("/").rsplit("/", 1)[-1]
        url_state = state.get(url_key, {})
        previous_hash = url_state.get("last_content_hash")

        print(f"\n--- {url_key[:40]} ---")

        try:
            html = fetch_page(url)
        except ScraperError as exc:
            print(f"  ERROR: {exc}")
            any_error = True
            continue

        result = analyze(html, previous_hash)
        title = extract_title(html)

        print(f"  Level: {result.alert_level}")
        print(f"  Hash changed: {result.hash_changed}")
        if result.pending_keywords_found:
            print(f"  Pending: {len(result.pending_keywords_found)} keywords")
        if result.ticket_keywords_found:
            print(f"  Keywords: {result.ticket_keywords_found}")
        if result.ticket_links_in_zone:
            print(f"  TICKET LINKS: {result.ticket_links_in_zone}")

        # Enviar alerta si corresponde
        if result.alert_level in ("high", "high_soldout"):
            last_alert = url_state.get("last_alert_type")
            if last_alert != result.alert_level:
                print(f"  >>> ENVIANDO ALERTA: {result.alert_reason}")
                send_alert(
                    alert_level=result.alert_level,
                    reason=result.alert_reason,
                    event_url=url,
                    event_name=title,
                    details={
                        "ticket_keywords": result.ticket_keywords_found,
                        "ticket_urls": result.ticket_urls_found,
                        "ticket_links": result.ticket_links_in_zone,
                        "soldout_keywords": result.soldout_keywords_found,
                    },
                )
                url_state["last_alert_type"] = result.alert_level
            else:
                print(f"  Alerta ya enviada previamente, skip.")

        elif result.alert_level == "medium" and result.hash_changed:
            last_hash_alert = url_state.get("last_change_alert_hash")
            if last_hash_alert != result.content_hash:
                print(f"  >>> ENVIANDO ALERTA CAMBIO")
                send_alert(
                    alert_level="medium",
                    reason=result.alert_reason,
                    event_url=url,
                    event_name=title,
                )
                url_state["last_change_alert_hash"] = result.content_hash

        url_state["last_content_hash"] = result.content_hash
        url_state["last_page_title"] = title
        state[url_key] = url_state

    state["total_checks"] = check_count
    save_state(state)

    if any_error:
        sys.exit(1)

    print("\nDone.")


if __name__ == "__main__":
    main()
