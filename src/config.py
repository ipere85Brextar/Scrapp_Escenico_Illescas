"""
Configuracion del servicio de monitorizacion.
Todas las variables son configurables via env vars con defaults sensatos.
"""

import os


# --- Target ---
# Lista de URLs a monitorizar (eventos individuales)
TARGET_URLS = [
    "https://elescenicodeillescas.es/juan-davila-illescas-2026-entradas-y-show-en-illescas",
    "https://elescenicodeillescas.es/pignoise-illescas-2026-entradas-y-concierto-en-illescas",
]

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_API_BASE = "https://api.telegram.org"

# --- GCP ---
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
FIRESTORE_COLLECTION = os.environ.get("FIRESTORE_COLLECTION", "scrapp_escenico")
FIRESTORE_DOCUMENT = "state"

# --- Cooldowns (minutos) ---
ALERT_COOLDOWN_MINUTES = int(os.environ.get("ALERT_COOLDOWN_MINUTES", "60"))
CHANGE_COOLDOWN_MINUTES = int(os.environ.get("CHANGE_COOLDOWN_MINUTES", "30"))

# --- HTTP ---
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "30"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "1"))
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# --- Errores ---
MAX_CONSECUTIVE_ERRORS = int(os.environ.get("MAX_CONSECUTIVE_ERRORS", "10"))

# --- Selectores CSS ---
# Selectores para extraer contenido relevante (en orden de prioridad)
# Basados en la estructura real del sitio (WordPress + Divi con clases esc-*)
CONTENT_SELECTORS = [
    ".esc-event",
    ".esc-ticket-box",
    ".esc-cta-box",
    "#main-content",
]

# Selectores a excluir del contenido (ruido)
EXCLUDE_SELECTORS = [
    "header",
    "footer",
    "nav",
    ".cookie-banner",
    "script",
    "style",
    ".social-media",
    "noscript",
    "iframe",
    ".esc-map-wrap",
]

# Selectores donde buscar links de compra de entradas
TICKET_LINK_SELECTORS = [
    ".esc-ticket-box",
    ".esc-cta-box",
    ".esc-btn",
]

# --- Keywords de deteccion ---

# Indican que HAY entradas a la venta (solo keywords que NO aparecen en estado "proximamente")
TICKET_POSITIVE_KEYWORDS = [
    "comprar entradas",
    "compra tu entrada",
    "adquirir entradas",
    "reservar entradas",
    "entradas disponibles",
    "entradas a la venta",
    "ya a la venta",
    "precio:",
    "precio entradas",
    "taquilla online",
    "añadir al carrito",
    "comprar ahora",
]

# Indican que las entradas AUN NO estan a la venta (estado actual de las paginas)
TICKET_PENDING_KEYWORDS = [
    "próximamente",
    "proximamente",
    "muy pronto",
    "en breve",
    "se activará",
    "se activara",
    "cargando venta",
    "disponible próximamente",
    "disponible proximamente",
]

# Dominios de plataformas de ticketing (regex para buscar en href de links)
TICKET_URL_PATTERNS = [
    r"entradas\.com",
    r"ticketmaster\.",
    r"atrapalo\.com",
    r"fever\.co",
    r"eventbrite\.",
    r"ticketea\.",
    r"wegow\.",
    r"seetickets\.",
    r"notikumi\.",
    r"kolondoo\.",
    r"giglon\.",
    r"tfranciscanos",
]

# Indican que las entradas EXISTEN pero estan AGOTADAS
TICKET_SOLDOUT_KEYWORDS = [
    "agotadas",
    "sold out",
    "no disponible",
    "completo",
    "sin entradas",
]
