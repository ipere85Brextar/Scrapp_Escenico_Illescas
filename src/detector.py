"""
Modulo de deteccion: analisis de cambios por hash y keywords.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from scraper import extract_content, extract_links
from config import (
    TICKET_POSITIVE_KEYWORDS,
    TICKET_SOLDOUT_KEYWORDS,
    TICKET_URL_PATTERNS,
)


@dataclass
class DetectionResult:
    """Resultado del analisis de una pagina."""

    content_hash: str
    hash_changed: bool
    ticket_keywords_found: list[str] = field(default_factory=list)
    ticket_urls_found: list[str] = field(default_factory=list)
    soldout_keywords_found: list[str] = field(default_factory=list)
    alert_level: str = "low"  # "high", "high_soldout", "medium", "low"
    alert_reason: str = ""


def analyze(html: str, previous_hash: str | None = None) -> DetectionResult:
    """
    Ejecuta ambas capas de deteccion sobre el HTML descargado.

    Args:
        html: HTML completo de la pagina.
        previous_hash: Hash SHA-256 del check anterior (None si es el primero).

    Returns:
        DetectionResult con el resultado del analisis.
    """
    # --- Capa 1: Hash ---
    content_text = extract_content(html)
    content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()

    if previous_hash is None:
        hash_changed = False  # Primer check, no hay referencia
    else:
        hash_changed = content_hash != previous_hash

    # --- Capa 2: Keywords ---
    ticket_keywords = _find_keywords(content_text, TICKET_POSITIVE_KEYWORDS)
    soldout_keywords = _find_keywords(content_text, TICKET_SOLDOUT_KEYWORDS)

    # --- Capa 2: URLs de ticketing ---
    links = extract_links(html)
    ticket_urls = _find_ticket_urls(links, TICKET_URL_PATTERNS)

    # --- Determinar nivel de alerta ---
    alert_level, alert_reason = _determine_alert_level(
        hash_changed=hash_changed,
        ticket_keywords=ticket_keywords,
        ticket_urls=ticket_urls,
        soldout_keywords=soldout_keywords,
        is_first_check=(previous_hash is None),
    )

    return DetectionResult(
        content_hash=content_hash,
        hash_changed=hash_changed,
        ticket_keywords_found=ticket_keywords,
        ticket_urls_found=ticket_urls,
        soldout_keywords_found=soldout_keywords,
        alert_level=alert_level,
        alert_reason=alert_reason,
    )


def _find_keywords(text: str, keywords: list[str]) -> list[str]:
    """Busca keywords en el texto (case-insensitive, ya normalizado a lower)."""
    found = []
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            found.append(kw)
    return found


def _find_ticket_urls(
    links: list[dict[str, str]], patterns: list[str]
) -> list[str]:
    """Busca URLs de plataformas de ticketing en los links extraidos."""
    found = []
    for link in links:
        href = link["href"].lower()
        for pattern in patterns:
            if re.search(pattern, href):
                found.append(link["href"])
                break
    return found


def _determine_alert_level(
    *,
    hash_changed: bool,
    ticket_keywords: list[str],
    ticket_urls: list[str],
    soldout_keywords: list[str],
    is_first_check: bool,
) -> tuple[str, str]:
    """
    Determina el nivel de alerta combinando hash + keywords.

    Returns:
        Tupla (alert_level, alert_reason).
    """
    has_tickets = bool(ticket_keywords) or bool(ticket_urls)
    has_soldout = bool(soldout_keywords)

    # Prioridad: entradas detectadas > agotadas > cambio generico > sin cambios
    if has_tickets and not has_soldout:
        parts = []
        if ticket_keywords:
            parts.append(f"Keywords: {', '.join(ticket_keywords)}")
        if ticket_urls:
            parts.append(f"URLs: {', '.join(ticket_urls)}")
        return "high", f"Entradas detectadas. {'; '.join(parts)}"

    if has_tickets and has_soldout:
        return "high_soldout", (
            f"Entradas detectadas pero aparecen como agotadas. "
            f"Soldout: {', '.join(soldout_keywords)}"
        )

    if has_soldout and not has_tickets:
        return "high_soldout", (
            f"Indicadores de entradas agotadas detectados: {', '.join(soldout_keywords)}"
        )

    if hash_changed and not is_first_check:
        return "medium", "El contenido de la pagina ha cambiado."

    return "low", "Sin cambios detectados."
