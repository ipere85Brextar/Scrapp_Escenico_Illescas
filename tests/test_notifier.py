"""
Tests para el modulo notifier (formateo de mensajes, sin envio real).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from notifier import _escape_md, _format_number, _format_alert_message, _format_heartbeat_message


class TestEscapeMd:
    """Tests para _escape_md."""

    def test_escapes_special_chars(self):
        assert _escape_md("hello_world") == "hello\\_world"
        assert _escape_md("precio: 15€") == "precio: 15€"  # : no es especial en MarkdownV2
        assert _escape_md("test.com") == "test\\.com"

    def test_no_special_chars(self):
        assert _escape_md("hola mundo") == "hola mundo"

    def test_multiple_special(self):
        result = _escape_md("[link](url)")
        assert "\\[" in result
        assert "\\]" in result
        assert "\\(" in result
        assert "\\)" in result


class TestFormatNumber:
    """Tests para _format_number."""

    def test_small_number(self):
        assert _format_number(42) == "42"

    def test_thousands(self):
        assert _format_number(14520) == "14\\.520"

    def test_zero(self):
        assert _format_number(0) == "0"


class TestFormatAlertMessage:
    """Tests para _format_alert_message."""

    def test_high_alert(self):
        msg = _format_alert_message(
            "high",
            "Entradas detectadas",
            {"ticket_keywords": ["comprar entradas"], "ticket_urls": ["https://entradas.com/x"]},
        )
        assert "ENTRADAS DETECTADAS" in msg
        assert "comprar entradas" in msg

    def test_soldout_alert(self):
        msg = _format_alert_message(
            "high_soldout",
            "Agotadas",
            {"soldout_keywords": ["agotadas"]},
        )
        assert "AGOTADAS" in msg

    def test_medium_alert(self):
        msg = _format_alert_message("medium", "Cambio", {})
        assert "CAMBIO DETECTADO" in msg

    def test_low_returns_empty(self):
        msg = _format_alert_message("low", "", {})
        assert msg == ""


class TestFormatHeartbeat:
    """Tests para _format_heartbeat_message."""

    def test_basic_heartbeat(self):
        stats = {
            "service_started_at": "6 abr 2026",
            "total_checks": 100,
            "total_changes_detected": 2,
            "total_alerts_sent": 1,
            "total_errors": 0,
            "last_check_at": "hace 1 min",
            "last_change_detected_at": "nunca",
        }
        msg = _format_heartbeat_message(stats)
        assert "Servicio activo" in msg
        assert "100" in msg
