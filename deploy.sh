#!/usr/bin/env bash
#
# Script de despliegue a GCP para Scrapp Escenico Illescas.
#
# Uso:
#   chmod +x deploy.sh
#   ./deploy.sh
#
# Requisitos:
#   - gcloud CLI instalado y autenticado
#   - Variables de entorno o editar los valores de abajo
#
set -euo pipefail

# ============================================================
# CONFIGURACION — Editar estos valores antes del primer deploy
# ============================================================
PROJECT_ID="${GCP_PROJECT_ID:-tu-proyecto-gcp}"
REGION="${GCP_REGION:-europe-west1}"
SERVICE_ACCOUNT="${SCRAPP_SA:-scrapp-escenico-sa@${PROJECT_ID}.iam.gserviceaccount.com}"
TELEGRAM_CHAT_ID_VALUE="${TELEGRAM_CHAT_ID:-}"

# Nombre del secreto en Secret Manager que contiene el token del bot
SECRET_NAME="telegram-scrapp-token"

# ============================================================
# 0. Seleccionar proyecto
# ============================================================
echo ">>> Seleccionando proyecto: ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}"

# ============================================================
# 1. Crear Service Account (si no existe)
# ============================================================
SA_NAME="scrapp-escenico-sa"
echo ">>> Creando Service Account: ${SA_NAME} (si no existe)"
gcloud iam service-accounts describe "${SERVICE_ACCOUNT}" 2>/dev/null || \
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="Scrapp Escenico SA"

# Asignar roles
for ROLE in roles/datastore.user roles/secretmanager.secretAccessor roles/logging.logWriter; do
  echo "    Asignando ${ROLE}"
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet
done

# ============================================================
# 2. Crear secreto de Telegram (si no existe)
# ============================================================
echo ">>> Verificando secreto: ${SECRET_NAME}"
if ! gcloud secrets describe "${SECRET_NAME}" --project="${PROJECT_ID}" 2>/dev/null; then
  echo "    Secreto no encontrado. Creandolo..."
  echo "    IMPORTANTE: Introduce el token de tu bot de Telegram:"
  read -rsp "    Token: " BOT_TOKEN
  echo
  echo -n "${BOT_TOKEN}" | gcloud secrets create "${SECRET_NAME}" \
    --data-file=- \
    --project="${PROJECT_ID}"
  echo "    Secreto creado."
else
  echo "    Secreto ya existe."
fi

# ============================================================
# 3. Deploy Cloud Function: check_page
# ============================================================
echo ">>> Desplegando Cloud Function: check-escenico"
gcloud functions deploy check-escenico \
  --gen2 \
  --region="${REGION}" \
  --runtime=python312 \
  --source=src/ \
  --entry-point=check_page \
  --trigger-http \
  --memory=256Mi \
  --timeout=60s \
  --max-instances=1 \
  --min-instances=0 \
  --no-allow-unauthenticated \
  --service-account="${SERVICE_ACCOUNT}" \
  --set-secrets="TELEGRAM_BOT_TOKEN=${SECRET_NAME}:latest" \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID_VALUE}" \
  --quiet

CHECK_URL=$(gcloud functions describe check-escenico --gen2 --region="${REGION}" --format='value(serviceConfig.uri)')
echo "    URL: ${CHECK_URL}"

# ============================================================
# 4. Deploy Cloud Function: send_heartbeat
# ============================================================
echo ">>> Desplegando Cloud Function: heartbeat-escenico"
gcloud functions deploy heartbeat-escenico \
  --gen2 \
  --region="${REGION}" \
  --runtime=python312 \
  --source=src/ \
  --entry-point=send_heartbeat \
  --trigger-http \
  --memory=256Mi \
  --timeout=30s \
  --max-instances=1 \
  --min-instances=0 \
  --no-allow-unauthenticated \
  --service-account="${SERVICE_ACCOUNT}" \
  --set-secrets="TELEGRAM_BOT_TOKEN=${SECRET_NAME}:latest" \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID_VALUE}" \
  --quiet

HEARTBEAT_URL=$(gcloud functions describe heartbeat-escenico --gen2 --region="${REGION}" --format='value(serviceConfig.uri)')
echo "    URL: ${HEARTBEAT_URL}"

# ============================================================
# 5. Cloud Scheduler: check cada minuto
# ============================================================
echo ">>> Creando Cloud Scheduler job: check-escenico-job"
gcloud scheduler jobs describe check-escenico-job --location="${REGION}" 2>/dev/null && \
  gcloud scheduler jobs update http check-escenico-job \
    --location="${REGION}" \
    --schedule="* * * * *" \
    --uri="${CHECK_URL}" \
    --http-method=POST \
    --oidc-service-account-email="${SERVICE_ACCOUNT}" \
    --time-zone="Europe/Madrid" \
    --quiet \
|| \
  gcloud scheduler jobs create http check-escenico-job \
    --location="${REGION}" \
    --schedule="* * * * *" \
    --uri="${CHECK_URL}" \
    --http-method=POST \
    --oidc-service-account-email="${SERVICE_ACCOUNT}" \
    --time-zone="Europe/Madrid" \
    --quiet

# ============================================================
# 6. Cloud Scheduler: heartbeat cada 4 horas
# ============================================================
echo ">>> Creando Cloud Scheduler job: heartbeat-escenico-job"
gcloud scheduler jobs describe heartbeat-escenico-job --location="${REGION}" 2>/dev/null && \
  gcloud scheduler jobs update http heartbeat-escenico-job \
    --location="${REGION}" \
    --schedule="0 */4 * * *" \
    --uri="${HEARTBEAT_URL}" \
    --http-method=POST \
    --oidc-service-account-email="${SERVICE_ACCOUNT}" \
    --time-zone="Europe/Madrid" \
    --quiet \
|| \
  gcloud scheduler jobs create http heartbeat-escenico-job \
    --location="${REGION}" \
    --schedule="0 */4 * * *" \
    --uri="${HEARTBEAT_URL}" \
    --http-method=POST \
    --oidc-service-account-email="${SERVICE_ACCOUNT}" \
    --time-zone="Europe/Madrid" \
    --quiet

# ============================================================
# DONE
# ============================================================
echo ""
echo "============================================"
echo "  Despliegue completado!"
echo "============================================"
echo "  Check URL:     ${CHECK_URL}"
echo "  Heartbeat URL: ${HEARTBEAT_URL}"
echo ""
echo "  Scheduler:"
echo "    - check-escenico-job:     cada 1 minuto"
echo "    - heartbeat-escenico-job: cada 4 horas"
echo ""
echo "  Para probar manualmente:"
echo "    curl -X POST ${CHECK_URL} -H \"Authorization: bearer \$(gcloud auth print-identity-token)\""
echo "============================================"
