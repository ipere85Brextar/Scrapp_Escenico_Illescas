"""
Configuracion del servicio de monitorizacion.
Todas las variables son configurables via env vars con defaults sensatos.
"""

import os


# --- Target ---
TARGET_URL = os.environ.get("TARGET_URL", "https://elescenicodeillescas.es/")

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_API_BASE = "https://api.telegram.org"

# --- GCP ---
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
FIRESTORE_COLLECTION = os.environ.get("FIRESTORE_COLLECTION", "scrapp_escenico")
FIRESTORE_DOCUMENT = "state"

# --- Cooldowns (minutos) ---
ALERT_COOLDOWN_MINUTES = int(os.environ.get("ALERT_COOLDOWN_MINUTES", "60"))
CHANGE_COOLDOWN_MINUTES = int(os.environ.get("CHANGE_COOLDOWN_MINUTES", "30"))

# --- HTTP ---
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "15"))
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
CONTENT_SELECTORS = [
    "main",
    ".content",
    ".programacion",
    ".eventos",
    "#content",
    "article",
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
]

# --- Keywords de deteccion ---

# Indican que HAY entradas a la venta
TICKET_POSITIVE_KEYWORDS = [
    "comprar entradas",
    "compra tu entrada",
    "venta de entradas",
    "adquirir entradas",
    "reservar entradas",
    "entradas disponibles",
    "entradas a la venta",
    "ya a la venta",
    "precio:",
    "precio entradas",
    "taquilla online",
    "punto de venta",
    "venta online",
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
