#!/bin/bash
# ==============================================================================
# setup_wine_mt5.sh – Setup Wine, Xvfb, and Python for Windows on Ubuntu
# ==============================================================================

set -euo pipefail

echo "======================================================"
echo " Starting Wine + MT5 + Python Adapter Setup"
echo "======================================================"

# 1. Install prerequisites
echo "[1] Installing Xvfb and Wine dependencies..."
sudo dpkg --add-architecture i386
sudo apt update
sudo DEBIAN_FRONTEND=noninteractive apt install -y xvfb wine64 wine32 wget winbind cabextract

# 2. Setup Wine prefix
export WINEPREFIX="$HOME/.wine_mt5"
export WINEARCH="win64"
echo "[2] Initializing Wine prefix at $WINEPREFIX..."
# wineboot initializes the prefix
wineboot -u
sleep 5

# 3. Install Python for Windows inside Wine
PYTHON_INSTALLER="python-3.11.8-amd64.exe"
echo "[3] Downloading Python for Windows ($PYTHON_INSTALLER)..."
cd /tmp
if [ ! -f "$PYTHON_INSTALLER" ]; then
    wget -q "https://www.python.org/ftp/python/3.11.8/$PYTHON_INSTALLER"
fi

echo "[4] Installing Python silently in Wine..."
# Install Python silently. Add to PATH inside Wine.
wine "$PYTHON_INSTALLER" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
sleep 10 # Wait for installation to finish

# 4. Install MT5 Python dependencies
echo "[5] Installing MetaTrader5 and Flask in Wine Python..."
# Python is usually installed in C:\Program Files\Python311\python.exe
# We'll use wine cmd to run pip
wine cmd /c "python -m pip install --upgrade pip"
wine cmd /c "python -m pip install MetaTrader5 Flask waitress pandas pytz requests"

echo "======================================================"
echo " Setup complete! Next steps:"
echo " 1. Download and run the Vantage MT5 installer via Wine:"
echo "    wine vantage_mt5setup.exe"
echo " 2. Install the systemd services in monitor/services/"
echo "======================================================"
