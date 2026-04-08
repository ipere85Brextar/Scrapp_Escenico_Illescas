#!/bin/bash
# Setup script for the VM - run once after SSH
set -euo pipefail

echo ">>> Installing Python and pip..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv > /dev/null

echo ">>> Creating app directory..."
mkdir -p ~/scrapp
cd ~/scrapp

echo ">>> Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo ">>> Installing dependencies..."
pip install -q httpx beautifulsoup4 lxml

echo ">>> Setup complete. Now copy the source files and .env, then run:"
echo "    cd ~/scrapp && source .venv/bin/activate && python3 run_local.py"
