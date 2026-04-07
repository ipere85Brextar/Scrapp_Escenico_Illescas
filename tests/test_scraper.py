"""
Tests para el modulo scraper.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from scraper import extract_content, extract_links, extract_ticket_links, extract_title, _normalize_text


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


class TestExtractContent:
    """Tests para extract_content."""

    def test_extracts_event_content(self):
        """Debe extraer contenido del .esc-event."""
        html = _load_fixture("sample_page.html")
        content = extract_content(html)

        assert "juan dávila" in content
        assert "illescas" in content
        assert "plaza de toros" in content

    def test_excludes_header_footer(self):
        """No debe incluir contenido de header/footer."""
        html = _load_fixture("sample_page.html")
        content = extract_content(html)

        assert "© 2026" not in content

    def test_excludes_map(self):
        """No debe incluir el mapa (.esc-map-wrap)."""
        html = _load_fixture("sample_page.html")
        content = extract_content(html)

        assert "cómo llegar" not in content

    def test_content_is_normalized(self):
        """El contenido debe estar normalizado (lowercase, sin espacios dobles)."""
        html = _load_fixture("sample_page.html")
        content = extract_content(html)

        assert content == content.lower()
        assert "  " not in content

    def test_with_tickets_page(self):
        """Debe extraer contenido de pagina con entradas."""
        html = _load_fixture("sample_page_with_tickets.html")
        content = extract_content(html)

        assert "comprar entradas" in content
        assert "entradas disponibles" in content

    def test_pending_keywords_present(self):
        """Pagina sin entradas debe tener keywords de pendiente."""
        html = _load_fixture("sample_page.html")
        content = extract_content(html)

        assert "próximamente" in content
        assert "muy pronto" in content


class TestExtractLinks:
    """Tests para extract_links."""

    def test_extracts_all_links(self):
        html = _load_fixture("sample_page_with_tickets.html")
        links = extract_links(html)

        hrefs = [l["href"] for l in links]
        assert any("entradas.com" in h for h in hrefs)

    def test_excludes_hash_links(self):
        html = '<html><body><a href="#">top</a><a href="/page">page</a></body></html>'
        links = extract_links(html)

        hrefs = [l["href"] for l in links]
        assert "#" not in hrefs
        assert "/page" in hrefs

    def test_text_is_lowercase(self):
        html = '<html><body><a href="/x">COMPRAR Entradas</a></body></html>'
        links = extract_links(html)

        assert links[0]["text"] == "comprar entradas"


class TestExtractTicketLinks:
    """Tests para extract_ticket_links."""

    def test_finds_links_in_ticket_box(self):
        """Debe encontrar links dentro de .esc-ticket-box."""
        html = _load_fixture("sample_page_with_tickets.html")
        links = extract_ticket_links(html)

        assert len(links) > 0
        assert any("entradas.com" in l["href"] for l in links)

    def test_no_links_in_pending_page(self):
        """Pagina 'proximamente' no debe tener links de compra en zona de entradas."""
        html = _load_fixture("sample_page.html")
        links = extract_ticket_links(html)

        assert len(links) == 0

    def test_deduplicates_links(self):
        """No debe duplicar el mismo link si aparece en ticket-box y cta-box."""
        html = _load_fixture("sample_page_with_tickets.html")
        links = extract_ticket_links(html)

        hrefs = [l["href"] for l in links]
        assert len(hrefs) == len(set(hrefs))


class TestExtractTitle:
    """Tests para extract_title."""

    def test_extracts_title(self):
        html = _load_fixture("sample_page.html")
        title = extract_title(html)
        assert "Escénico de Illescas" in title

    def test_no_title(self):
        html = "<html><body>hola</body></html>"
        title = extract_title(html)
        assert title == ""


class TestNormalizeText:
    """Tests para _normalize_text."""

    def test_lowercase(self):
        assert _normalize_text("HOLA Mundo") == "hola mundo"

    def test_collapse_spaces(self):
        assert _normalize_text("hola    mundo") == "hola mundo"

    def test_strip(self):
        assert _normalize_text("  hola  ") == "hola"

    def test_newlines_to_space(self):
        assert _normalize_text("hola\n\nmundo") == "hola mundo"
