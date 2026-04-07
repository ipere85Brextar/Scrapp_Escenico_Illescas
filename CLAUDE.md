# Scrapp Escenico Illescas

## Qué es

Servicio serverless que monitoriza [elescenicodeillescas.es](https://elescenicodeillescas.es/) cada minuto para detectar cuando salen entradas a la venta y notifica por Telegram. Incluye heartbeat cada 4h.

## Stack

- **Runtime:** Cloud Functions 2nd gen, Python 3.12
- **Scheduler:** Cloud Scheduler (check cada 1 min + heartbeat cada 4h)
- **Estado:** Cloud Firestore (colección `scrapp_escenico`, documento `state`)
- **Notificaciones:** Telegram Bot API via httpx (POST directo, sin polling)
- **Secretos:** GCP Secret Manager
- **Parsing:** BeautifulSoup4 + lxml
- **Región:** europe-west1

## Estructura del proyecto

```
src/
  main.py        # Entry points: check_page() y send_heartbeat()
  config.py      # Settings (env vars + constantes, keywords, selectores)
  scraper.py     # Descarga HTML y parsing con BeautifulSoup
  detector.py    # Detección doble capa: hash SHA-256 + keywords/URLs
  notifier.py    # Envío mensajes Telegram
  state.py       # CRUD estado en Firestore
tests/
  test_detector.py
  test_scraper.py
  fixtures/sample_page.html
requirements.txt
deploy.sh
arquitectura.md  # Documento de arquitectura detallado
```

## Lógica de detección (doble capa)

1. **Hash:** SHA-256 del contenido normalizado. Detecta cualquier cambio en la página.
2. **Keywords/URLs:** Busca keywords de venta de entradas y URLs de plataformas de ticketing en los links.

### Niveles de alerta

- **ALTO:** Keywords de entradas positivos detectados → mensaje inmediato
- **ALTO (sold out):** Keywords de agotadas → mensaje informativo
- **MEDIO:** Hash cambió sin keywords → cambio genérico detectado
- **BAJO:** Sin cambios → solo log

### Cooldown anti-spam

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

# Despliegue manual
gcloud functions deploy check-escenico --gen2 --region=europe-west1 --runtime=python312 --entry-point=check_page --trigger-http
gcloud functions deploy heartbeat-escenico --gen2 --region=europe-west1 --runtime=python312 --entry-point=send_heartbeat --trigger-http
```

## Variables de entorno necesarias

- `TELEGRAM_BOT_TOKEN` — desde Secret Manager
- `TELEGRAM_CHAT_ID` — ID del chat de Telegram
- `GCP_PROJECT_ID` — proyecto de GCP

## Convenciones

- No se usa `python-telegram-bot`: solo se envían mensajes con httpx directo a la API
- Manejo de errores: reintentar 1 vez si la página no responde, incrementar `consecutive_errors`, alertar solo si supera `MAX_CONSECUTIVE_ERRORS = 10`
- Toda la configuración centralizada en `config.py` con defaults sensatos
- El documento `arquitectura.md` contiene la especificación completa del proyecto
