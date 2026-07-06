#!/bin/bash
# ==============================================================================
# setup_mt5_services.sh – Install systemd services for Headless MT5 & Adapter
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_DIR="$PROJECT_DIR/monitor/services"
mkdir -p "$SERVICE_DIR"

USER=$(whoami)
WINEPREFIX="$HOME/.wine_mt5"

echo "Generating systemd services for $USER..."

# 1. Xvfb Service (Virtual Display)
cat <<EOF > "$SERVICE_DIR/xvfb.service"
[Unit]
Description=Xvfb Virtual Display Server
After=network.target

[Service]
ExecStart=/usr/bin/Xvfb :99 -screen 0 1024x768x24
User=$USER
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 2. MT5 Terminal Service
cat <<EOF > "$SERVICE_DIR/mt5_terminal.service"
[Unit]
Description=MetaTrader 5 Terminal under Wine
Requires=xvfb.service
After=xvfb.service

[Service]
Environment=DISPLAY=:99
Environment=WINEPREFIX=$WINEPREFIX
Environment=WINEARCH=win64
# Adjust the path to terminal64.exe if needed based on Vantage installation path
ExecStart=/usr/bin/wine "$WINEPREFIX/drive_c/Program Files/Vantage FX MT5/terminal64.exe" /portable
User=$USER
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 3. MT5 Python REST Adapter Service
cat <<EOF > "$SERVICE_DIR/mt5_adapter.service"
[Unit]
Description=MT5 Python REST Adapter (Flask via Wine)
Requires=mt5_terminal.service
After=mt5_terminal.service

[Service]
Environment=DISPLAY=:99
Environment=WINEPREFIX=$WINEPREFIX
Environment=WINEARCH=win64
WorkingDirectory=$PROJECT_DIR
# Python must be in PATH inside the Wine prefix. 
ExecStart=/usr/bin/wine cmd /c "python mt5_adapter/server.py"
User=$USER
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "Installing services to /etc/systemd/system/ (requires sudo)..."
sudo cp "$SERVICE_DIR"/*.service /etc/systemd/system/
sudo systemctl daemon-reload

echo "Done! You can start them with:"
echo "  sudo systemctl start xvfb mt5_terminal mt5_adapter"
echo "  sudo systemctl enable xvfb mt5_terminal mt5_adapter"
