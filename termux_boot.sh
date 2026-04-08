#!/bin/bash
# Script de arranque automatico para Termux:Boot
# Se ejecuta al iniciar el dispositivo si Termux:Boot esta instalado

termux-wake-lock
cd ~/scrapp && python run_local.py >> ~/scrapp/scrapp.log 2>&1 &
