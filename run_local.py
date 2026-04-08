"""
Ejecuta el check en bucle local (cada 60 segundos).
Usa .env para las variables de entorno.
No requiere Firestore: usa un fichero JSON local como estado.
"""

import sys
import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "src")

# Cargar .env manualmente
env_path = Path(".env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            import os
            os.environ.setdefault(key.strip(), value.strip())

from config import TARGET_URLS
from scraper import fetch_page, extract_title, ScraperError
from detector import analyze
from notifier import send_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_local")

STATE_FILE = Path("local_state.json")
CHECK_INTERVAL = 60  # segundos


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def main():
    logger.info("Iniciando monitor local. Check cada %d segundos.", CHECK_INTERVAL)
    logger.info("URLs: %s", TARGET_URLS)
    logger.info("Ctrl+C para detener.\n")

    state = load_state()
    check_count = state.get("total_checks", 0)

    while True:
        check_count += 1
        now = datetime.now(timezone.utc)
        logger.info("--- Check #%d ---", check_count)

        for url in TARGET_URLS:
            url_key = url.rstrip("/").rsplit("/", 1)[-1]
            url_state = state.get(url_key, {})
            previous_hash = url_state.get("last_content_hash")

            try:
                html = fetch_page(url)
            except ScraperError as exc:
                logger.error("[%s] Error descargando: %s", url_key[:30], exc)
                continue

            result = analyze(html, previous_hash)
            title = extract_title(html)

            # Log del resultado
            status_parts = [f"level={result.alert_level}"]
            if result.hash_changed:
                status_parts.append("HASH_CHANGED")
            if result.pending_keywords_found:
                status_parts.append(f"pending={len(result.pending_keywords_found)}")
            if result.ticket_keywords_found:
                status_parts.append(f"keywords={result.ticket_keywords_found}")
            if result.ticket_links_in_zone:
                status_parts.append(f"LINKS={result.ticket_links_in_zone}")

            logger.info("[%s] %s", url_key[:30], " | ".join(status_parts))

            # Enviar alerta si corresponde
            if result.alert_level in ("high", "high_soldout"):
                last_alert = url_state.get("last_alert_type")
                if last_alert != result.alert_level:
                    logger.info("[%s] ENVIANDO ALERTA: %s", url_key[:30], result.alert_reason)
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

            elif result.alert_level == "medium" and result.hash_changed:
                last_change_alert = url_state.get("last_change_alert_hash")
                if last_change_alert != result.content_hash:
                    logger.info("[%s] ENVIANDO ALERTA CAMBIO: %s", url_key[:30], result.alert_reason)
                    send_alert(
                        alert_level="medium",
                        reason=result.alert_reason,
                        event_url=url,
                        event_name=title,
                    )
                    url_state["last_change_alert_hash"] = result.content_hash

            # Actualizar estado
            url_state["last_content_hash"] = result.content_hash
            url_state["last_check_at"] = now.isoformat()
            url_state["last_page_title"] = title
            state[url_key] = url_state

        state["total_checks"] = check_count
        state["last_check_at"] = now.isoformat()
        save_state(state)

        logger.info("Siguiente check en %d segundos...\n", CHECK_INTERVAL)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nMonitor detenido.")
