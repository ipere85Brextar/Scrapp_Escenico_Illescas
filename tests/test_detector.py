"""
Tests para el modulo detector.
"""

import sys
import os
from pathlib import Path

# Agregar src/ al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from detector import analyze, _find_keywords, _find_ticket_urls


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    """Carga un fichero HTML de fixtures."""
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


# --- Tests de analyze() ---


class TestAnalyze:
    """Tests para la funcion principal analyze()."""

    def test_first_check_no_previous_hash(self):
        """Primer check: no hay hash previo, level debe ser low."""
        html = _load_fixture("sample_page.html")
        result = analyze(html, previous_hash=None)

        assert result.content_hash  # Tiene hash
        assert result.hash_changed is False  # Primer check, no hay referencia
        assert result.alert_level == "low"
        assert result.ticket_keywords_found == []
        assert result.ticket_urls_found == []

    def test_no_change_same_html(self):
        """Dos checks con el mismo HTML: sin cambios."""
        html = _load_fixture("sample_page.html")
        first = analyze(html, previous_hash=None)
        second = analyze(html, previous_hash=first.content_hash)

        assert second.hash_changed is False
        assert second.alert_level == "low"
        assert second.content_hash == first.content_hash

    def test_change_detected_different_html(self):
        """HTML diferente debe detectar cambio."""
        html_before = _load_fixture("sample_page.html")
        html_after = _load_fixture("sample_page_with_tickets.html")

        first = analyze(html_before, previous_hash=None)
        second = analyze(html_after, previous_hash=first.content_hash)

        assert second.hash_changed is True

    def test_tickets_detected(self):
        """Pagina con entradas debe dar alert_level=high."""
        html = _load_fixture("sample_page_with_tickets.html")
        result = analyze(html, previous_hash=None)

        assert result.alert_level == "high"
        assert len(result.ticket_keywords_found) > 0
        assert any("comprar entradas" in kw for kw in result.ticket_keywords_found)

    def test_ticket_urls_detected(self):
        """Debe detectar URLs de plataformas de ticketing."""
        html = _load_fixture("sample_page_with_tickets.html")
        result = analyze(html, previous_hash=None)

        assert len(result.ticket_urls_found) > 0
        assert any("entradas.com" in url for url in result.ticket_urls_found)

    def test_soldout_detected(self):
        """Pagina con entradas agotadas debe dar alert_level=high_soldout."""
        html = _load_fixture("sample_page_soldout.html")
        result = analyze(html, previous_hash=None)

        assert result.alert_level == "high_soldout"
        assert len(result.soldout_keywords_found) > 0
        assert any("agotadas" in kw for kw in result.soldout_keywords_found)

    def test_venta_online_keyword(self):
        """'venta online' debe detectarse como keyword positivo."""
        html = _load_fixture("sample_page_with_tickets.html")
        result = analyze(html, previous_hash=None)

        assert "venta online" in result.ticket_keywords_found

    def test_hash_is_deterministic(self):
        """Mismo HTML siempre produce el mismo hash."""
        html = _load_fixture("sample_page.html")
        r1 = analyze(html)
        r2 = analyze(html)
        assert r1.content_hash == r2.content_hash


# --- Tests de helpers ---


class TestFindKeywords:
    """Tests para _find_keywords."""

    def test_finds_exact_match(self):
        text = "las entradas estan disponibles para comprar entradas en taquilla"
        found = _find_keywords(text, ["comprar entradas", "reservar entradas"])
        assert "comprar entradas" in found
        assert "reservar entradas" not in found

    def test_case_insensitive(self):
        text = "COMPRAR ENTRADAS ahora"
        found = _find_keywords(text, ["comprar entradas"])
        assert "comprar entradas" in found

    def test_no_match(self):
        text = "informacion general del teatro"
        found = _find_keywords(text, ["comprar entradas", "venta online"])
        assert found == []

    def test_venta_online(self):
        text = "venta online disponible"
        found = _find_keywords(text, ["venta online", "comprar entradas"])
        assert "venta online" in found


class TestFindTicketUrls:
    """Tests para _find_ticket_urls."""

    def test_finds_entradas_com(self):
        links = [
            {"href": "https://www.entradas.com/event/123", "text": "comprar"},
            {"href": "https://facebook.com/page", "text": "facebook"},
        ]
        found = _find_ticket_urls(links, [r"entradas\.com", r"ticketmaster\."])
        assert len(found) == 1
        assert "entradas.com" in found[0]

    def test_no_ticket_urls(self):
        links = [
            {"href": "https://facebook.com/page", "text": "facebook"},
            {"href": "https://instagram.com/page", "text": "instagram"},
        ]
        found = _find_ticket_urls(links, [r"entradas\.com", r"ticketmaster\."])
        assert found == []

    def test_multiple_platforms(self):
        links = [
            {"href": "https://www.entradas.com/event/123", "text": "comprar"},
            {"href": "https://www.eventbrite.es/event/456", "text": "reservar"},
        ]
        found = _find_ticket_urls(
            links, [r"entradas\.com", r"eventbrite\."]
        )
        assert len(found) == 2
