"""
Modulo de scraping: descarga y parsing de la pagina web.
"""

from __future__ import annotations

import logging
import re
import unicodedata

import httpx
from bs4 import BeautifulSoup

from config import (
    CONTENT_SELECTORS,
    EXCLUDE_SELECTORS,
    MAX_RETRIES,
    REQUEST_TIMEOUT_SECONDS,
    TICKET_LINK_SELECTORS,
    USER_AGENT,
)

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    """Error al descargar o parsear la pagina."""


def fetch_page(url: str, timeout: int | None = None) -> str:
    """
    Descarga el HTML completo de la pagina.

    Args:
        url: URL a descargar.
        timeout: Timeout en segundos (default: REQUEST_TIMEOUT_SECONDS).

    Returns:
        HTML como string.

    Raises:
        ScraperError: Si no se puede descargar tras los reintentos.
    """
    timeout = timeout or REQUEST_TIMEOUT_SECONDS
    headers = {"User-Agent": USER_AGENT}
    last_error = None

    for attempt in range(1 + MAX_RETRIES):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                return response.text
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_error = exc
            logger.warning(
                "Intento %d/%d fallido para %s: %s",
                attempt + 1,
                1 + MAX_RETRIES,
                url,
                exc,
            )

    raise ScraperError(
        f"No se pudo descargar {url} tras {1 + MAX_RETRIES} intentos: {last_error}"
    )


def extract_content(
    html: str,
    selectors: list[str] | None = None,
    exclude: list[str] | None = None,
) -> str:
    """
    Extrae el contenido relevante del HTML, normalizado.

    1. Parsea con BeautifulSoup.
    2. Elimina elementos de exclude_selectors.
    3. Busca contenido en content_selectors (en orden, usa el primero que exista).
    4. Si ningun selector coincide, usa body completo.
    5. Normaliza: lowercase, elimina espacios multiples, strip.

    Returns:
        Texto normalizado del contenido principal.
    """
    selectors = selectors or CONTENT_SELECTORS
    exclude = exclude or EXCLUDE_SELECTORS

    soup = BeautifulSoup(html, "lxml")

    # Eliminar elementos ruidosos
    for sel in exclude:
        for element in soup.select(sel):
            element.decompose()

    # Buscar contenido principal por selectores
    content_element = None
    for sel in selectors:
        found = soup.select_one(sel)
        if found:
            content_element = found
            break

    # Fallback: body completo
    if content_element is None:
        content_element = soup.body or soup

    raw_text = content_element.get_text(separator=" ", strip=True)
    return _normalize_text(raw_text)


def extract_links(html: str) -> list[dict[str, str]]:
    """
    Extrae todos los links (<a href>) con su texto y URL.

    Returns:
        Lista de dicts con keys: "href", "text".
    """
    soup = BeautifulSoup(html, "lxml")
    links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        text = a_tag.get_text(strip=True)
        if href and not href.startswith("#"):
            links.append({"href": href, "text": text.lower()})
    return links


def extract_ticket_links(
    html: str,
    selectors: list[str] | None = None,
) -> list[dict[str, str]]:
    """
    Extrae links solo de las zonas de entradas (.esc-ticket-box, .esc-cta-box, .esc-btn).
    Un link externo aqui es la senal principal de que las entradas estan a la venta.

    Returns:
        Lista de dicts con keys: "href", "text".
    """
    selectors = selectors or TICKET_LINK_SELECTORS
    soup = BeautifulSoup(html, "lxml")
    links = []
    seen = set()

    for sel in selectors:
        for container in soup.select(sel):
            for a_tag in container.find_all("a", href=True):
                href = a_tag["href"].strip()
                text = a_tag.get_text(strip=True)
                if (
                    href
                    and not href.startswith("#")
                    and href.startswith("http")
                    and href not in seen
                ):
                    links.append({"href": href, "text": text.lower()})
                    seen.add(href)
    return links


def extract_title(html: str) -> str:
    """Extrae el <title> de la pagina."""
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find("title")
    return title_tag.get_text(strip=True) if title_tag else ""


def _normalize_text(text: str) -> str:
    """Normaliza texto: NFC, lowercase, colapsar espacios."""
    text = unicodedata.normalize("NFC", text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()
