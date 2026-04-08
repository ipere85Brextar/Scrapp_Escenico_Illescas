#!/bin/bash
# Setup completo para Termux - copiar y pegar todo de una vez
set -e

echo ">>> Instalando Python..."
pkg install -y python git

echo ">>> Clonando repositorio..."
cd ~
git clone https://github.com/ipere85Brextar/Scrapp_Escenico_Illescas.git scrapp
cd scrapp

echo ">>> Instalando dependencias..."
pip install httpx beautifulsoup4 lxml

echo ">>> Creando fichero .env..."
cat > .env << 'ENVEOF'
TELEGRAM_BOT_TOKEN=8746533989:AAEXrOTbrydLtaqARXLM6mzey5PJcC5MClM
TELEGRAM_CHAT_ID=6375668523
GCP_PROJECT_ID=scrapp-escenico-ill
ENVEOF

echo ""
echo "========================================="
echo "  Setup completado!"
echo "========================================="
echo ""
echo "  Para arrancar el monitor:"
echo "    cd ~/scrapp && python run_local.py"
echo ""
echo "  Para que arranque al abrir Termux:"
echo "    mkdir -p ~/.termux/boot"
echo "    cp ~/scrapp/termux_boot.sh ~/.termux/boot/"
echo "    Instala Termux:Boot desde F-Droid"
echo "========================================="
