# Scrapp Escenico Illescas - Arquitectura del Proyecto

## Objetivo

Servicio de monitorización automática de la web [elescenicodeillescas.es](https://elescenicodeillescas.es/) que detecta cuanto salen entradas a la venta y notifica inmediatamente via Telegram. Incluye heartbeat cada 4 horas para confirmar que el servicio sigue activo.

---

## Stack Tecnologico

| Componente | Tecnologia | Justificacion |
|---|---|---|
| Runtime | Cloud Functions 2nd gen (Python 3.12) | Serverless, sin infraestructura que mantener, free tier generoso |
| Scheduler | Cloud Scheduler | 2 jobs: check cada minuto + heartbeat cada 4h |
| Estado | Cloud Firestore | Almacena ultimo hash, timestamps, contadores |
| Notificaciones | Telegram Bot API (via httpx) | Envio directo de mensajes, sin polling |
| Secretos | GCP Secret Manager | Token del bot de Telegram |
| Parsing HTML | BeautifulSoup4 + lxml | Extraccion de contenido y deteccion de elementos |

---

## Arquitectura General

```
Cloud Scheduler                         Cloud Scheduler
(cada 1 minuto)                         (cada 4 horas)
      |                                       |
      v                                       v
  HTTP POST                               HTTP POST
  /check                                  /heartbeat
      |                                       |
      v                                       v
+---------------------------+    +---------------------------+
|   Cloud Function          |    |   Cloud Function          |
|   "check_page"            |    |   "send_heartbeat"        |
|                           |    |                           |
|  1. Fetch pagina          |    |  1. Leer estado actual    |
|  2. Extraer contenido     |    |  2. Calcular stats        |
|  3. Calcular hash         |    |  3. Enviar resumen TG     |
|  4. Comparar con anterior |    +---------------------------+
|  5. Buscar keywords       |
|  6. Si alerta -> TG msg   |
|  7. Actualizar estado     |
+---------------------------+
      |             |
      v             v
  Firestore    Telegram Bot API
  (estado)     (notificaciones)
```

---

## Estrategia de Deteccion (Doble Capa)

### Capa 1: Deteccion por Hash (cambio general)

Detecta CUALQUIER cambio en la pagina. Es la red de seguridad: aunque no sepamos exactamente donde aparecen las entradas, si la pagina cambia, nos enteramos.

```
Flujo:
1. Descargar HTML completo de la pagina
2. Extraer el contenido principal (eliminar headers, footers, timestamps, scripts)
3. Normalizar: lowercase, eliminar espacios multiples, strip whitespace
4. Calcular SHA-256 del contenido normalizado
5. Comparar con hash almacenado en Firestore
6. Si difiere -> alerta nivel MEDIO (cambio detectado)
```

**Selectores CSS configurables** para extraer solo el contenido relevante (hay que ajustarlos al ver la pagina real):

```python
CONTENT_SELECTORS = [
    "main",
    ".content",
    ".programacion",
    ".eventos",
    "#content",
    "article",
]

EXCLUDE_SELECTORS = [
    "header",
    "footer",
    "nav",
    ".cookie-banner",
    "script",
    "style",
    ".social-media",
]
```

### Capa 2: Deteccion por Keywords/Elementos (entradas especificas)

Busca indicadores directos de venta de entradas. Es la deteccion precisa: si encuentra estos patrones, es casi seguro que hay entradas.

```python
# Keywords que indican que HAY entradas a la venta
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

# Dominios de plataformas de ticketing (buscar en href de links)
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
    r"tfranciscanos",          # Compra local illescas?
]

# Keywords que indican que las entradas EXISTEN pero estan AGOTADAS
TICKET_SOLDOUT_KEYWORDS = [
    "agotadas",
    "sold out",
    "no disponible",
    "completo",
    "sin entradas",
]
```

### Niveles de Alerta

| Nivel | Condicion | Accion Telegram |
|---|---|---|
| ALTO | Keywords de entradas positivos detectados | Mensaje inmediato con detalle |
| ALTO (sold out) | Keywords de agotadas detectados | Mensaje informativo de que hay entradas pero agotadas |
| MEDIO | Hash cambio pero sin keywords de entradas | Mensaje informativo de cambio en la pagina |
| BAJO | Sin cambios | No se envia nada (solo log) |

### Cooldown Anti-Spam

Para no recibir el mismo mensaje cada minuto una vez que se detecta un cambio:

```
- ALERT_COOLDOWN_MINUTES = 60     # No repetir la MISMA alerta en 60 min
- CHANGE_COOLDOWN_MINUTES = 30    # No repetir "pagina cambio" en 30 min
- Cada alerta registra timestamp + tipo en Firestore
- Antes de enviar, verificar que no se envio la misma alerta dentro del cooldown
```

---

## Modelo de Estado (Firestore)

### Coleccion: `scrapp_escenico`

**Documento: `state`**

```json
{
  "last_content_hash": "sha256...",
  "last_check_at": "2026-04-06T10:30:00Z",
  "last_change_detected_at": "2026-04-05T14:22:00Z",
  "last_alert_sent_at": "2026-04-05T14:22:00Z",
  "last_alert_type": "ticket_keywords",
  "last_heartbeat_at": "2026-04-06T08:00:00Z",
  "total_checks": 14520,
  "total_changes_detected": 3,
  "total_alerts_sent": 2,
  "total_errors": 0,
  "consecutive_errors": 0,
  "last_error": null,
  "last_error_at": null,
  "last_page_title": "El Escenico de Illescas",
  "last_ticket_keywords_found": [],
  "last_ticket_urls_found": [],
  "service_started_at": "2026-04-06T00:00:00Z"
}
```

---

## Estructura del Proyecto

```
scrapp_escenico_illescas/
├── arquitectura.md              # Este documento
├── src/
│   ├── main.py                  # Entry points Cloud Functions (check_page, send_heartbeat)
│   ├── config.py                # Settings (env vars + constantes)
│   ├── scraper.py               # Descarga y parsing de la pagina
│   ├── detector.py              # Logica de deteccion (hash + keywords)
│   ├── notifier.py              # Envio de mensajes Telegram
│   └── state.py                 # CRUD estado en Firestore
├── tests/
│   ├── test_detector.py         # Tests de deteccion con HTML de ejemplo
│   ├── test_scraper.py          # Tests de parsing
│   └── fixtures/
│       └── sample_page.html     # HTML de ejemplo para tests
├── requirements.txt
├── .env.example
└── deploy.sh                    # Script de despliegue a GCP
```

---

## Descripcion de Modulos

### `main.py` — Entry Points

Dos funciones HTTP que Cloud Scheduler invoca:

```python
# POST /check  → Cloud Scheduler cada 1 minuto
def check_page(request):
    """
    1. Descargar pagina con scraper.fetch_page()
    2. Ejecutar detector.analyze(html)
       - Retorna: hash, keywords_found, urls_found, alert_level
    3. Leer estado anterior de state.get_state()
    4. Comparar hash actual vs anterior
    5. Evaluar nivel de alerta combinando hash + keywords
    6. Si alerta y fuera de cooldown -> notifier.send_alert(...)
    7. Actualizar estado con state.update_state(...)
    8. Return 200 OK
    """

# POST /heartbeat  → Cloud Scheduler cada 4 horas
def send_heartbeat(request):
    """
    1. Leer estado de state.get_state()
    2. Calcular stats: tiempo activo, checks totales, ultimo cambio
    3. notifier.send_heartbeat(stats)
    4. Actualizar last_heartbeat_at
    5. Return 200 OK
    """
```

### `scraper.py` — Descarga y Parsing

```python
def fetch_page(url: str, timeout: int = 15) -> str:
    """
    Descarga el HTML de la pagina.
    - User-Agent realista (navegador)
    - Timeout configurable (default 15s)
    - Retry 1 vez si falla
    - Lanza ScraperError si no se puede descargar
    """

def extract_content(html: str, selectors: list, exclude: list) -> str:
    """
    Extrae el contenido relevante del HTML:
    1. Parsear con BeautifulSoup
    2. Eliminar elementos de EXCLUDE_SELECTORS
    3. Buscar contenido en CONTENT_SELECTORS (en orden, usar el primero que exista)
    4. Si ningun selector coincide, usar body completo
    5. Extraer texto normalizado
    """

def extract_links(html: str) -> list[dict]:
    """
    Extrae todos los links (<a href>) con su texto y URL.
    Util para detectar links a plataformas de ticketing.
    """
```

### `detector.py` — Logica de Deteccion

```python
@dataclass
class DetectionResult:
    content_hash: str
    hash_changed: bool
    ticket_keywords_found: list[str]
    ticket_urls_found: list[str]
    soldout_keywords_found: list[str]
    alert_level: str            # "high", "medium", "low"
    alert_reason: str           # Descripcion legible del motivo

def analyze(html: str, previous_hash: str | None) -> DetectionResult:
    """
    Ejecuta ambas capas de deteccion:
    1. Extraer contenido y calcular hash
    2. Comparar con hash anterior
    3. Buscar ticket keywords en texto
    4. Buscar ticket URL patterns en links
    5. Buscar soldout keywords
    6. Determinar alert_level segun combinacion
    """
```

### `notifier.py` — Telegram

```python
def send_alert(alert_level: str, reason: str, details: dict) -> bool:
    """
    Envia alerta al chat de Telegram.
    Formato del mensaje segun nivel:

    ALTO (entradas detectadas):
      🎫🔴 ENTRADAS DETECTADAS - El Escenico de Illescas
      Keywords encontrados: comprar entradas, precio
      URLs de ticketing: entradas.com/...
      🔗 https://elescenicodeillescas.es/

    ALTO (agotadas):
      🎫🟠 ENTRADAS AGOTADAS - El Escenico de Illescas
      Se detectaron entradas pero aparecen como agotadas
      🔗 https://elescenicodeillescas.es/

    MEDIO (cambio pagina):
      📄🟡 CAMBIO DETECTADO - El Escenico de Illescas
      La pagina ha cambiado. Puede que haya novedades.
      🔗 https://elescenicodeillescas.es/
    """

def send_heartbeat(stats: dict) -> bool:
    """
    Envia mensaje de heartbeat:

      💚 Servicio activo - Scrapp Escenico
      ⏱ Activo desde: 6 abr 2026, 00:00
      🔍 Checks realizados: 14.520
      📊 Cambios detectados: 3
      🕐 Ultimo check: hace 1 min
      📅 Ultimo cambio: 5 abr 2026, 14:22
    """
```

### `state.py` — Persistencia

```python
def get_state() -> dict:
    """Lee el documento state de Firestore. Si no existe, retorna estado inicial."""

def update_state(updates: dict) -> None:
    """Actualiza campos del estado. Merge, no overwrite."""

def is_within_cooldown(alert_type: str, cooldown_minutes: int) -> bool:
    """Verifica si una alerta del mismo tipo se envio dentro del cooldown."""

def increment_counters(checks: int = 0, changes: int = 0, alerts: int = 0, errors: int = 0) -> None:
    """Incrementa contadores atomicamente."""
```

### `config.py` — Configuracion

```python
# Todas las variables configurables via env vars con defaults sensatos:

TARGET_URL = "https://elescenicodeillescas.es/"
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN")      # Desde Secret Manager
TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID")

GCP_PROJECT_ID = env("GCP_PROJECT_ID")
FIRESTORE_COLLECTION = "scrapp_escenico"

ALERT_COOLDOWN_MINUTES = 60
CHANGE_COOLDOWN_MINUTES = 30

REQUEST_TIMEOUT_SECONDS = 15
MAX_RETRIES = 1
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36..."

CONTENT_SELECTORS = [...]        # Los listados arriba
EXCLUDE_SELECTORS = [...]
TICKET_POSITIVE_KEYWORDS = [...]
TICKET_URL_PATTERNS = [...]
TICKET_SOLDOUT_KEYWORDS = [...]

MAX_CONSECUTIVE_ERRORS = 10      # Alerta si errores consecutivos superan este numero
```

---

## Manejo de Errores

| Escenario | Comportamiento |
|---|---|
| Pagina no responde (timeout/5xx) | Incrementar `consecutive_errors`. NO alertar. Reintentar 1 vez. |
| N errores consecutivos > MAX_CONSECUTIVE_ERRORS | Enviar alerta Telegram: "Servicio degradado, la pagina no responde desde hace X minutos" |
| Pagina responde pero HTML vacio/raro | Loguear warning, no alertar, no actualizar hash |
| Error de Firestore | Loguear, continuar sin estado (el proximo check compensara) |
| Error enviando Telegram | Loguear error, NO reintentar (el proximo ciclo lo hara) |
| Cloud Function timeout (>60s) | Cloud Scheduler reintenta automaticamente en el siguiente ciclo |

Cuando `consecutive_errors` se resetea a 0 tras un check exitoso, si venia de un estado degradado se envia: "Servicio recuperado. La pagina vuelve a responder."

---

## Despliegue en GCP

### Recursos a crear

```bash
# 1. Cloud Functions (2nd gen)
gcloud functions deploy check-escenico \
  --gen2 \
  --region=europe-west1 \
  --runtime=python312 \
  --entry-point=check_page \
  --trigger-http \
  --memory=256Mi \
  --timeout=60s \
  --max-instances=1 \
  --min-instances=0 \
  --no-allow-unauthenticated \
  --set-secrets="TELEGRAM_BOT_TOKEN=telegram-scrapp-token:latest"

gcloud functions deploy heartbeat-escenico \
  --gen2 \
  --region=europe-west1 \
  --runtime=python312 \
  --entry-point=send_heartbeat \
  --trigger-http \
  --memory=256Mi \
  --timeout=30s \
  --max-instances=1 \
  --min-instances=0 \
  --no-allow-unauthenticated \
  --set-secrets="TELEGRAM_BOT_TOKEN=telegram-scrapp-token:latest"

# 2. Cloud Scheduler - Check cada minuto
gcloud scheduler jobs create http check-escenico-job \
  --location=europe-west1 \
  --schedule="* * * * *" \
  --uri="FUNCTION_URL/check" \
  --http-method=POST \
  --oidc-service-account-email=SCHEDULER_SA@PROJECT.iam.gserviceaccount.com \
  --time-zone="Europe/Madrid"

# 3. Cloud Scheduler - Heartbeat cada 4 horas
gcloud scheduler jobs create http heartbeat-escenico-job \
  --location=europe-west1 \
  --schedule="0 */4 * * *" \
  --uri="FUNCTION_URL/heartbeat" \
  --http-method=POST \
  --oidc-service-account-email=SCHEDULER_SA@PROJECT.iam.gserviceaccount.com \
  --time-zone="Europe/Madrid"

# 4. Firestore (si no existe)
gcloud firestore databases create --location=europe-west1

# 5. Secret Manager
echo -n "TU_BOT_TOKEN" | gcloud secrets create telegram-scrapp-token --data-file=-
```

### Service Account

```
scrapp-escenico-sa@PROJECT.iam.gserviceaccount.com

Roles:
  - roles/datastore.user          (Firestore read/write)
  - roles/secretmanager.secretAccessor  (leer token Telegram)
  - roles/logging.logWriter       (Cloud Logging)
```

---

## Dependencias

```
# requirements.txt
functions-framework==3.*
google-cloud-firestore==2.*
httpx==0.27.*
beautifulsoup4==4.*
lxml==5.*
```

Nota: NO se usa `python-telegram-bot` porque solo enviamos mensajes (no recibimos). Un POST directo con httpx a `api.telegram.org/botTOKEN/sendMessage` es mas ligero y simple.

---

## Configuracion de Telegram

Pasos previos al despliegue:

1. Crear bot en Telegram con @BotFather → obtener TOKEN
2. Enviar un mensaje al bot desde tu cuenta
3. Obtener tu CHAT_ID via `https://api.telegram.org/botTOKEN/getUpdates`
4. Guardar TOKEN en Secret Manager
5. Configurar CHAT_ID como env var de la Cloud Function

---

## Estimacion de Costes

| Recurso | Uso mensual | Coste |
|---|---|---|
| Cloud Functions | ~44.640 invocaciones (1/min + heartbeats) | $0 (free tier: 2M/mes) |
| Cloud Functions compute | ~256MB x 5s x 44.640 = ~22.320 GB-s | $0 (free tier: 400K GB-s) |
| Cloud Scheduler | 2 jobs | $0 (free tier: 3 jobs) |
| Firestore | ~90.000 reads + 45.000 writes / mes | $0 (free tier: 50K reads/dia) |
| Networking (egress) | ~50MB/mes (HTML descargado) | $0 |
| Secret Manager | ~45.000 accesos/mes | $0 (free tier: 10K accesos) |
| **TOTAL** | | **~$0/mes** |

Todo encaja dentro del free tier de GCP para este volumen de uso.

---

## Orden de Implementacion Sugerido

### Fase 0: Preparacion (~30 min)
1. Crear bot de Telegram y obtener token + chat_id
2. Inspeccionar la pagina web manualmente y anotar selectores CSS relevantes
3. Crear proyecto GCP (o usar uno existente)

### Fase 1: Core local (~2h)
4. `config.py` — configuracion
5. `scraper.py` — descarga y parsing
6. `detector.py` — logica de deteccion
7. `notifier.py` — envio Telegram
8. Test local: ejecutar manualmente y verificar que detecta y notifica

### Fase 2: Persistencia + Cloud Functions (~1h)
9. `state.py` — Firestore
10. `main.py` — entry points como Cloud Functions
11. `requirements.txt`

### Fase 3: Despliegue (~1h)
12. `deploy.sh` — script de despliegue
13. Crear recursos GCP (Scheduler, Secret Manager, service account)
14. Deploy y verificar que funciona en la nube

### Fase 4: Ajuste fino (~30 min)
15. Afinar selectores CSS tras ver la pagina real
16. Ajustar keywords si es necesario
17. Probar todos los niveles de alerta
18. Verificar heartbeat

---

## Decisiones Pendientes

Las siguientes decisiones requieren inspeccion manual de la pagina:

1. **Selectores CSS**: Hay que ver la estructura real del HTML para definir que parte de la pagina monitorizar y cual ignorar.
2. **Keywords adicionales**: Puede que la pagina use terminologia especifica (ej: "reservas" en vez de "entradas").
3. **Subpaginas**: Decidir si monitorizar solo la home o tambien subpaginas de programacion.
4. **Pagina de entradas separada**: Puede que las entradas se vendan en una URL distinta (ej: /entradas o /programacion). Si es asi, monitorizar esa URL tambien.
