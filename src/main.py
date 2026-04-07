"""
Entry points para Cloud Functions 2nd gen.

Dos funciones HTTP:
  - check_page: Cloud Scheduler cada 1 minuto
  - send_heartbeat: Cloud Scheduler cada 4 horas
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import functions_framework
from flask import Request

from config import (
    ALERT_COOLDOWN_MINUTES,
    CHANGE_COOLDOWN_MINUTES,
    MAX_CONSECUTIVE_ERRORS,
    TARGET_URLS,
)
from scraper import ScraperError, fetch_page, extract_title
from detector import analyze
from notifier import (
    send_alert,
    send_error_alert,
    send_recovery_alert,
)
from notifier import send_heartbeat as _notify_heartbeat
from state import (
    get_state,
    increment_consecutive_errors,
    increment_counters,
    is_within_cooldown,
    reset_consecutive_errors,
    update_state,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@functions_framework.http
def check_page(request: Request) -> tuple[str, int]:
    """
    Cloud Function: comprueba todas las paginas de eventos y envia alertas si procede.

    Itera sobre TARGET_URLS y analiza cada una independientemente.
    """
    logger.info("Iniciando check de %d URLs", len(TARGET_URLS))
    now = datetime.now(timezone.utc)
    results = []

    for url in TARGET_URLS:
        result = _check_single_url(url, now)
        results.append(result)

    return f'{{"status": "ok", "results": {results}}}', 200


def _check_single_url(url: str, now: datetime) -> dict:
    """Comprueba una URL individual."""
    logger.info("Checking %s", url)

    # Usar un sufijo del URL como clave para el estado de cada evento
    url_key = url.rstrip("/").rsplit("/", 1)[-1]

    # Leer estado previo
    prev_state = get_state()
    url_states = prev_state.get("url_states", {})
    url_state = url_states.get(url_key, {})
    previous_hash = url_state.get("last_content_hash")
    was_degraded = prev_state.get("consecutive_errors", 0) >= MAX_CONSECUTIVE_ERRORS

    # --- Paso 1: Descargar pagina ---
    try:
        html = fetch_page(url)
    except ScraperError as exc:
        logger.error("Error descargando %s: %s", url, exc)
        consecutive = increment_consecutive_errors()
        increment_counters(checks=1, errors=1)
        update_state({
            "last_check_at": now,
            "last_error": str(exc),
            "last_error_at": now,
        })

        if consecutive == MAX_CONSECUTIVE_ERRORS:
            send_error_alert(str(exc), consecutive)

        return {"url": url, "status": "error"}

    # --- Paso 2: Analizar ---
    result = analyze(html, previous_hash)
    page_title = extract_title(html)

    logger.info(
        "[%s] level=%s, hash_changed=%s, keywords=%s, ticket_links=%s, pending=%s",
        url_key,
        result.alert_level,
        result.hash_changed,
        result.ticket_keywords_found,
        result.ticket_links_in_zone,
        result.pending_keywords_found,
    )

    # --- Recuperacion tras errores ---
    if was_degraded:
        reset_consecutive_errors()
        send_recovery_alert()
    elif prev_state.get("consecutive_errors", 0) > 0:
        reset_consecutive_errors()

    # --- Paso 3: Enviar alerta si corresponde ---
    alert_sent = False
    cooldown_key = f"{result.alert_level}_{url_key}"

    if result.alert_level == "high":
        if not is_within_cooldown(cooldown_key, ALERT_COOLDOWN_MINUTES):
            alert_sent = send_alert(
                alert_level="high",
                reason=result.alert_reason,
                event_url=url,
                event_name=page_title,
                details={
                    "ticket_keywords": result.ticket_keywords_found,
                    "ticket_urls": result.ticket_urls_found,
                    "ticket_links": result.ticket_links_in_zone,
                },
            )

    elif result.alert_level == "high_soldout":
        if not is_within_cooldown(cooldown_key, ALERT_COOLDOWN_MINUTES):
            alert_sent = send_alert(
                alert_level="high_soldout",
                reason=result.alert_reason,
                event_url=url,
                event_name=page_title,
                details={
                    "soldout_keywords": result.soldout_keywords_found,
                },
            )

    elif result.alert_level == "medium":
        if not is_within_cooldown(cooldown_key, CHANGE_COOLDOWN_MINUTES):
            alert_sent = send_alert(
                alert_level="medium",
                reason=result.alert_reason,
                event_url=url,
                event_name=page_title,
            )

    # --- Paso 4: Actualizar estado por URL ---
    new_url_state = {
        "last_content_hash": result.content_hash,
        "last_check_at": now.isoformat(),
        "last_page_title": page_title,
    }
    if result.hash_changed:
        new_url_state["last_change_detected_at"] = now.isoformat()
    if result.ticket_keywords_found:
        new_url_state["last_ticket_keywords_found"] = result.ticket_keywords_found
    if result.ticket_links_in_zone:
        new_url_state["last_ticket_links_found"] = result.ticket_links_in_zone
    if result.pending_keywords_found:
        new_url_state["last_pending_keywords_found"] = result.pending_keywords_found

    url_states[url_key] = new_url_state

    state_updates: dict = {
        "last_check_at": now,
        "url_states": url_states,
    }

    if result.hash_changed:
        state_updates["last_change_detected_at"] = now
        increment_counters(checks=1, changes=1)
    else:
        increment_counters(checks=1)

    if alert_sent:
        state_updates["last_alert_sent_at"] = now
        state_updates["last_alert_type"] = cooldown_key
        increment_counters(alerts=1)

    update_state(state_updates)

    return {
        "url": url,
        "status": "ok",
        "alert_level": result.alert_level,
        "alert_sent": alert_sent,
    }


@functions_framework.http
def send_heartbeat(request: Request) -> tuple[str, int]:
    """
    Cloud Function: envia mensaje de heartbeat con stats del servicio.
    """
    logger.info("Enviando heartbeat.")
    now = datetime.now(timezone.utc)
    state = get_state()

    success = _notify_heartbeat(state)

    if success:
        update_state({"last_heartbeat_at": now})

    status = "ok" if success else "error"
    return f'{{"status": "{status}"}}', 200
