#!/bin/bash
# ==============================================================================
# Freqtrade Bot Service Restart
# Restarts Freqtrade service using systemd or Docker Compose.
# ==============================================================================

set -uo pipefail

MONITOR_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_DIR="$(dirname "$MONITOR_DIR")"

echo "Initiating Freqtrade restart..."

if systemctl is-active freqtrade &>/dev/null; then
    echo "Restarting via systemd..."
    sudo systemctl restart freqtrade
else
    echo "systemd service not active. Restarting via Docker Compose directly..."
    cd "$PROJECT_DIR"
    docker compose down
    docker compose up -d
fi

echo "Restart command executed."
