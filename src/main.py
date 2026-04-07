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
    TARGET_URL,
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
    Cloud Function: comprueba la pagina y envia alertas si procede.

    Flujo:
      1. Descargar pagina
      2. Analizar (hash + keywords)
      3. Comparar con estado anterior
      4. Enviar alerta si corresponde (respetando cooldown)
      5. Actualizar estado
    """
    logger.info("Iniciando check de %s", TARGET_URL)
    now = datetime.now(timezone.utc)

    # Leer estado previo
    prev_state = get_state()
    previous_hash = prev_state.get("last_content_hash")
    was_degraded = prev_state.get("consecutive_errors", 0) >= MAX_CONSECUTIVE_ERRORS

    # --- Paso 1: Descargar pagina ---
    try:
        html = fetch_page(TARGET_URL)
    except ScraperError as exc:
        logger.error("Error descargando pagina: %s", exc)
        consecutive = increment_consecutive_errors()
        increment_counters(checks=1, errors=1)
        update_state({
            "last_check_at": now,
            "last_error": str(exc),
            "last_error_at": now,
        })

        # Alertar si superamos el umbral de errores consecutivos
        if consecutive == MAX_CONSECUTIVE_ERRORS:
            send_error_alert(str(exc), consecutive)

        return '{"status": "error", "reason": "fetch_failed"}', 200

    # --- Paso 2: Analizar ---
    result = analyze(html, previous_hash)
    page_title = extract_title(html)

    logger.info(
        "Analisis completado: level=%s, hash_changed=%s, keywords=%s",
        result.alert_level,
        result.hash_changed,
        result.ticket_keywords_found,
    )

    # --- Recuperacion tras errores ---
    if was_degraded:
        reset_consecutive_errors()
        send_recovery_alert()
        logger.info("Servicio recuperado tras periodo de errores.")
    elif prev_state.get("consecutive_errors", 0) > 0:
        reset_consecutive_errors()

    # --- Paso 3: Enviar alerta si corresponde ---
    alert_sent = False

    if result.alert_level == "high":
        if not is_within_cooldown("high", ALERT_COOLDOWN_MINUTES):
            alert_sent = send_alert(
                alert_level="high",
                reason=result.alert_reason,
                details={
                    "ticket_keywords": result.ticket_keywords_found,
                    "ticket_urls": result.ticket_urls_found,
                },
            )

    elif result.alert_level == "high_soldout":
        if not is_within_cooldown("high_soldout", ALERT_COOLDOWN_MINUTES):
            alert_sent = send_alert(
                alert_level="high_soldout",
                reason=result.alert_reason,
                details={
                    "soldout_keywords": result.soldout_keywords_found,
                },
            )

    elif result.alert_level == "medium":
        if not is_within_cooldown("medium", CHANGE_COOLDOWN_MINUTES):
            alert_sent = send_alert(
                alert_level="medium",
                reason=result.alert_reason,
            )

    # --- Paso 4: Actualizar estado ---
    state_updates: dict = {
        "last_content_hash": result.content_hash,
        "last_check_at": now,
        "last_page_title": page_title,
    }

    if result.hash_changed:
        state_updates["last_change_detected_at"] = now
        increment_counters(checks=1, changes=1)
    else:
        increment_counters(checks=1)

    if result.ticket_keywords_found:
        state_updates["last_ticket_keywords_found"] = result.ticket_keywords_found
    if result.ticket_urls_found:
        state_updates["last_ticket_urls_found"] = result.ticket_urls_found

    if alert_sent:
        state_updates["last_alert_sent_at"] = now
        state_updates["last_alert_type"] = result.alert_level
        increment_counters(alerts=1)

    update_state(state_updates)

    return f'{{"status": "ok", "alert_level": "{result.alert_level}", "alert_sent": {str(alert_sent).lower()}}}', 200


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
