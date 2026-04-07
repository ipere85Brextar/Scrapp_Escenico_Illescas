"""
Tests para el modulo scraper.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from scraper import extract_content, extract_links, extract_title, _normalize_text


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


class TestExtractContent:
    """Tests para extract_content."""

    def test_extracts_main_content(self):
        """Debe extraer contenido del <main> tag."""
        html = _load_fixture("sample_page.html")
        content = extract_content(html)

        assert "programación 2026" in content
        assert "rey león" in content
        assert "concierto de primavera" in content

    def test_excludes_header_footer(self):
        """No debe incluir contenido de header/footer."""
        html = _load_fixture("sample_page.html")
        content = extract_content(html)

        # El nav link "Inicio" esta en el header, que se excluye
        # El copyright esta en footer, que se excluye
        assert "© 2026" not in content

    def test_excludes_social_media(self):
        """No debe incluir links de redes sociales del footer."""
        html = _load_fixture("sample_page.html")
        content = extract_content(html)

        assert "facebook" not in content
        assert "instagram" not in content

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
        assert "venta online" in content

    def test_custom_selectors(self):
        """Debe respetar selectores custom."""
        html = _load_fixture("sample_page.html")
        # Solo extraer del article
        content = extract_content(html, selectors=["article"], exclude=[])

        assert "rey león" in content


class TestExtractLinks:
    """Tests para extract_links."""

    def test_extracts_all_links(self):
        html = _load_fixture("sample_page_with_tickets.html")
        links = extract_links(html)

        # Debe tener links de nav + ticket + social
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
