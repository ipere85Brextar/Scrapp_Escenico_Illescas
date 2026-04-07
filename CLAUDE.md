# Scrapp Escenico Illescas

## Qué es

Servicio serverless que monitoriza páginas de eventos de [elescenicodeillescas.es](https://elescenicodeillescas.es/) cada minuto para detectar cuando salen entradas a la venta y notifica por Telegram. Incluye heartbeat cada 4h.

## URLs monitorizadas

- Juan Dávila: `https://elescenicodeillescas.es/juan-davila-illescas-2026-entradas-y-show-en-illescas`
- Pignoise: `https://elescenicodeillescas.es/pignoise-illescas-2026-entradas-y-concierto-en-illescas`

## Stack

- **Runtime:** Cloud Functions 2nd gen, Python 3.12
- **Scheduler:** Cloud Scheduler (check cada 1 min + heartbeat cada 4h)
- **Estado:** Cloud Firestore (colección `scrapp_escenico`, documento `state`)
- **Notificaciones:** Telegram Bot API via httpx (POST directo, sin polling)
- **Secretos:** GCP Secret Manager
- **Parsing:** BeautifulSoup4 + lxml
- **Región:** europe-west1
- **Proyecto GCP:** `scrapp-escenico-ill` (org: brextarsolutions-org)

## Estructura del proyecto

```
src/
  main.py        # Entry points: check_page() y send_heartbeat()
  config.py      # Settings (env vars + constantes, keywords, selectores)
  scraper.py     # Descarga HTML y parsing con BeautifulSoup
  detector.py    # Detección triple capa: hash + keywords + links en zona de entradas
  notifier.py    # Envío mensajes Telegram
  state.py       # CRUD estado en Firestore
tests/
  test_detector.py
  test_scraper.py
  test_notifier.py
  fixtures/      # HTMLs de ejemplo y páginas reales descargadas
doc/
  arquitectura.md
requirements.txt
deploy.sh
```

## Estructura del sitio web (WordPress + Divi)

Las páginas usan clases CSS custom con prefijo `esc-`:
- `.esc-event` — contenedor principal del evento
- `.esc-ticket-box` — zona de entradas (aquí aparecerá el link de compra)
- `.esc-cta-box` — call-to-action
- `.esc-btn` — botones de acción
- `.esc-coming-tag` — etiqueta "Próximamente"
- `.esc-loader-wrap` — barra de estado de carga

## Lógica de detección (triple capa)

1. **Hash:** SHA-256 del contenido normalizado de `.esc-event`. Detecta cualquier cambio.
2. **Keywords:** Busca keywords de venta vs pending vs agotadas. Keywords como "venta online" NO se usan porque ya aparecen en estado "próximamente".
3. **Links en zona de entradas:** Un link externo dentro de `.esc-ticket-box`, `.esc-cta-box` o `.esc-btn` es la señal principal de que las entradas están a la venta.

### Niveles de alerta

- **ALTO:** Link de compra detectado en zona de entradas o keywords positivos sin pending → mensaje inmediato
- **ALTO (sold out):** Keywords de agotadas → mensaje informativo
- **MEDIO:** Hash cambió (cambio genérico)
- **BAJO:** Sin cambios → solo log

### Cooldown anti-spam (por URL)

- `ALERT_COOLDOWN_MINUTES = 60` (misma alerta)
- `CHANGE_COOLDOWN_MINUTES = 30` (cambio de página)

## Dependencias

```
functions-framework==3.*
google-cloud-firestore==2.*
httpx==0.27.*
beautifulsoup4==4.*
lxml==5.*
```

## Comandos

```bash
# Tests
pytest tests/

# Deploy
bash deploy.sh

# Despliegue manual (via powershell, gcloud no funciona desde bash en este entorno)
gcloud functions deploy check-escenico --gen2 --region=europe-west1 --runtime=python312 --entry-point=check_page --trigger-http
gcloud functions deploy heartbeat-escenico --gen2 --region=europe-west1 --runtime=python312 --entry-point=send_heartbeat --trigger-http
```

## Variables de entorno necesarias

- `TELEGRAM_BOT_TOKEN` — desde Secret Manager
- `TELEGRAM_CHAT_ID` — ID del chat de Telegram (`6375668523`)
- `GCP_PROJECT_ID` — `scrapp-escenico-ill`

## Convenciones

- No se usa `python-telegram-bot`: solo se envían mensajes con httpx directo a la API
- Manejo de errores: reintentar 1 vez si la página no responde, incrementar `consecutive_errors`, alertar solo si supera `MAX_CONSECUTIVE_ERRORS = 10`
- Toda la configuración centralizada en `config.py` con defaults sensatos
- El documento `doc/arquitectura.md` contiene la especificación original del proyecto
- Los comandos gcloud deben ejecutarse via `powershell.exe -Command "..."` desde este entorno
