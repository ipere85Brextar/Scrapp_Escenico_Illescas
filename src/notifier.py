"""
Modulo de notificaciones: envio de mensajes via Telegram Bot API.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from config import TELEGRAM_API_BASE, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TARGET_URL

logger = logging.getLogger(__name__)


class NotifierError(Exception):
    """Error al enviar mensaje de Telegram."""


def send_alert(alert_level: str, reason: str, details: dict | None = None) -> bool:
    """
    Envia una alerta al chat de Telegram segun el nivel.

    Args:
        alert_level: "high", "high_soldout", "medium".
        reason: Descripcion legible del motivo.
        details: Dict opcional con keys: ticket_keywords, ticket_urls, soldout_keywords.

    Returns:
        True si se envio correctamente, False si hubo error.
    """
    details = details or {}
    message = _format_alert_message(alert_level, reason, details)
    return _send_telegram_message(message)


def send_heartbeat(stats: dict) -> bool:
    """
    Envia mensaje de heartbeat con estadisticas del servicio.

    Args:
        stats: Dict con keys: service_started_at, total_checks, total_changes_detected,
               total_alerts_sent, last_check_at, last_change_detected_at,
               consecutive_errors, total_errors.

    Returns:
        True si se envio correctamente.
    """
    message = _format_heartbeat_message(stats)
    return _send_telegram_message(message)


def send_error_alert(error_message: str, consecutive_errors: int) -> bool:
    """
    Envia alerta de servicio degradado.

    Args:
        error_message: Descripcion del error.
        consecutive_errors: Numero de errores consecutivos.

    Returns:
        True si se envio correctamente.
    """
    message = (
        f"⚠️ *SERVICIO DEGRADADO \\- Scrapp Escenico*\n\n"
        f"La pagina no responde\\.\n"
        f"Errores consecutivos: {consecutive_errors}\n"
        f"Ultimo error: {_escape_md(error_message)}\n\n"
        f"Se reintentara automaticamente\\."
    )
    return _send_telegram_message(message)


def send_recovery_alert() -> bool:
    """Envia alerta de recuperacion tras un periodo de errores."""
    message = (
        "✅ *SERVICIO RECUPERADO \\- Scrapp Escenico*\n\n"
        "La pagina vuelve a responder con normalidad\\."
    )
    return _send_telegram_message(message)


# --- Formateo de mensajes ---


def _format_alert_message(alert_level: str, reason: str, details: dict) -> str:
    """Construye el mensaje de alerta formateado en MarkdownV2."""

    if alert_level == "high":
        header = "🎫🔴 *ENTRADAS DETECTADAS \\- El Escenico de Illescas*"
        body_parts = [_escape_md(reason)]
        if details.get("ticket_keywords"):
            kws = ", ".join(details["ticket_keywords"])
            body_parts.append(f"Keywords: {_escape_md(kws)}")
        if details.get("ticket_urls"):
            urls = "\n".join(details["ticket_urls"])
            body_parts.append(f"URLs de ticketing:\n{_escape_md(urls)}")

    elif alert_level == "high_soldout":
        header = "🎫🟠 *ENTRADAS AGOTADAS \\- El Escenico de Illescas*"
        body_parts = [_escape_md(reason)]
        if details.get("soldout_keywords"):
            kws = ", ".join(details["soldout_keywords"])
            body_parts.append(f"Indicadores: {_escape_md(kws)}")

    elif alert_level == "medium":
        header = "📄🟡 *CAMBIO DETECTADO \\- El Escenico de Illescas*"
        body_parts = [
            "La pagina ha cambiado\\. Puede que haya novedades\\.",
        ]

    else:
        return ""

    link = _escape_md(TARGET_URL)
    body = "\n".join(body_parts)
    return f"{header}\n\n{body}\n\n🔗 {link}"


def _format_heartbeat_message(stats: dict) -> str:
    """Construye el mensaje de heartbeat formateado en MarkdownV2."""
    started = stats.get("service_started_at", "desconocido")
    if isinstance(started, datetime):
        started = started.strftime("%d %b %Y, %H:%M")

    total_checks = stats.get("total_checks", 0)
    total_changes = stats.get("total_changes_detected", 0)
    total_alerts = stats.get("total_alerts_sent", 0)
    total_errors = stats.get("total_errors", 0)

    last_check = stats.get("last_check_at")
    if isinstance(last_check, datetime):
        now = datetime.now(timezone.utc)
        diff = now - last_check
        minutes_ago = int(diff.total_seconds() / 60)
        last_check_str = f"hace {minutes_ago} min" if minutes_ago < 60 else last_check.strftime("%d %b %Y, %H:%M")
    else:
        last_check_str = str(last_check or "nunca")

    last_change = stats.get("last_change_detected_at")
    if isinstance(last_change, datetime):
        last_change_str = last_change.strftime("%d %b %Y, %H:%M")
    else:
        last_change_str = str(last_change or "ninguno")

    lines = [
        "💚 *Servicio activo \\- Scrapp Escenico*",
        "",
        f"⏱ Activo desde: {_escape_md(str(started))}",
        f"🔍 Checks realizados: {_format_number(total_checks)}",
        f"📊 Cambios detectados: {total_changes}",
        f"🚨 Alertas enviadas: {total_alerts}",
        f"❌ Errores totales: {total_errors}",
        f"🕐 Ultimo check: {_escape_md(last_check_str)}",
        f"📅 Ultimo cambio: {_escape_md(last_change_str)}",
    ]
    return "\n".join(lines)


# --- Helpers ---


def _send_telegram_message(text: str) -> bool:
    """
    Envia un mensaje via Telegram Bot API (sendMessage).

    Returns:
        True si status 200, False en caso contrario.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados.")
        return False

    url = f"{TELEGRAM_API_BASE}/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": False,
    }

    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(url, json=payload)

        if response.status_code == 200:
            logger.info("Mensaje Telegram enviado correctamente.")
            return True

        logger.error(
            "Error enviando Telegram: status=%d, body=%s",
            response.status_code,
            response.text,
        )
        return False

    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.error("Excepcion enviando Telegram: %s", exc)
        return False


def _escape_md(text: str) -> str:
    """Escapa caracteres especiales para MarkdownV2 de Telegram."""
    special_chars = r"_*[]()~`>#+-=|{}.!"
    escaped = ""
    for char in text:
        if char in special_chars:
            escaped += f"\\{char}"
        else:
            escaped += char
    return escaped


def _format_number(n: int) -> str:
    """Formatea numero con separador de miles (punto)."""
    return f"{n:,}".replace(",", "\\.")
