"""
Modulo de estado: persistencia en Cloud Firestore.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from google.cloud import firestore

from config import FIRESTORE_COLLECTION, FIRESTORE_DOCUMENT, GCP_PROJECT_ID

logger = logging.getLogger(__name__)

# Cliente Firestore (singleton a nivel de modulo, reutilizado entre invocaciones)
_db: firestore.Client | None = None


def _get_db() -> firestore.Client:
    """Obtiene el cliente Firestore (lazy init)."""
    global _db
    if _db is None:
        kwargs = {}
        if GCP_PROJECT_ID:
            kwargs["project"] = GCP_PROJECT_ID
        _db = firestore.Client(**kwargs)
    return _db


def _get_doc_ref() -> firestore.DocumentReference:
    """Referencia al documento de estado."""
    return _get_db().collection(FIRESTORE_COLLECTION).document(FIRESTORE_DOCUMENT)


# --- Estado inicial ---

INITIAL_STATE = {
    "last_content_hash": None,
    "last_check_at": None,
    "last_change_detected_at": None,
    "last_alert_sent_at": None,
    "last_alert_type": None,
    "last_heartbeat_at": None,
    "total_checks": 0,
    "total_changes_detected": 0,
    "total_alerts_sent": 0,
    "total_errors": 0,
    "consecutive_errors": 0,
    "last_error": None,
    "last_error_at": None,
    "last_page_title": "",
    "last_ticket_keywords_found": [],
    "last_ticket_urls_found": [],
    "service_started_at": datetime.now(timezone.utc),
}


# --- CRUD ---


def get_state() -> dict:
    """
    Lee el documento de estado de Firestore.
    Si no existe, lo crea con el estado inicial y lo retorna.
    """
    try:
        doc = _get_doc_ref().get()
        if doc.exists:
            return doc.to_dict()

        # Primera ejecucion: crear estado inicial
        _get_doc_ref().set(INITIAL_STATE)
        return dict(INITIAL_STATE)

    except Exception as exc:
        logger.error("Error leyendo estado de Firestore: %s", exc)
        return dict(INITIAL_STATE)


def update_state(updates: dict) -> None:
    """
    Actualiza campos del estado (merge, no overwrite).

    Args:
        updates: Dict con los campos a actualizar.
    """
    try:
        _get_doc_ref().set(updates, merge=True)
    except Exception as exc:
        logger.error("Error actualizando estado en Firestore: %s", exc)


def is_within_cooldown(alert_type: str, cooldown_minutes: int) -> bool:
    """
    Verifica si una alerta del mismo tipo se envio dentro del cooldown.

    Args:
        alert_type: Tipo de alerta ("high", "high_soldout", "medium").
        cooldown_minutes: Minutos de cooldown.

    Returns:
        True si estamos dentro del cooldown (NO enviar), False si se puede enviar.
    """
    state = get_state()
    last_type = state.get("last_alert_type")
    last_sent = state.get("last_alert_sent_at")

    if last_type != alert_type or last_sent is None:
        return False

    if isinstance(last_sent, datetime):
        now = datetime.now(timezone.utc)
        elapsed_minutes = (now - last_sent).total_seconds() / 60
        return elapsed_minutes < cooldown_minutes

    return False


def increment_counters(
    checks: int = 0,
    changes: int = 0,
    alerts: int = 0,
    errors: int = 0,
) -> None:
    """
    Incrementa contadores atomicamente usando Firestore increments.

    Args:
        checks: Incremento para total_checks.
        changes: Incremento para total_changes_detected.
        alerts: Incremento para total_alerts_sent.
        errors: Incremento para total_errors.
    """
    updates = {}
    if checks:
        updates["total_checks"] = firestore.Increment(checks)
    if changes:
        updates["total_changes_detected"] = firestore.Increment(changes)
    if alerts:
        updates["total_alerts_sent"] = firestore.Increment(alerts)
    if errors:
        updates["total_errors"] = firestore.Increment(errors)

    if updates:
        try:
            _get_doc_ref().update(updates)
        except Exception as exc:
            logger.error("Error incrementando contadores: %s", exc)


def reset_consecutive_errors() -> None:
    """Resetea el contador de errores consecutivos a 0."""
    update_state({"consecutive_errors": 0})


def increment_consecutive_errors() -> int:
    """
    Incrementa errores consecutivos y retorna el nuevo valor.

    Returns:
        Numero de errores consecutivos tras el incremento.
    """
    try:
        _get_doc_ref().update(
            {"consecutive_errors": firestore.Increment(1)}
        )
        state = get_state()
        return state.get("consecutive_errors", 1)
    except Exception as exc:
        logger.error("Error incrementando errores consecutivos: %s", exc)
        return 1
