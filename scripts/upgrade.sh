#!/bin/bash
# ==============================================================================
# Freqtrade Automated Upgrade Script
# Pulls the latest stable docker containers and restarts the application.
# ==============================================================================

set -euo pipefail

SCRIPTS_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_DIR="$(dirname "$SCRIPTS_DIR")"
LOG_FILE="$PROJECT_DIR/logs/upgrade.log"

mkdir -p "$PROJECT_DIR/logs"

echo "$(date '+%Y-%m-%d %H:%M:%S') - [INFO] - Commencing Freqtrade bot upgrade..." >> "$LOG_FILE"

echo "Pulling latest docker images..."
if ! docker compose -f "$PROJECT_DIR/docker-compose.yml" pull; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [ERROR] - Failed to pull latest Docker images." >> "$LOG_FILE"
    echo "Error: Docker compose pull failed."
    exit 1
fi

echo "Restarting service to apply updates..."
if systemctl is-active freqtrade &>/dev/null; then
    if ! sudo systemctl restart freqtrade; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - [ERROR] - Failed to restart systemd service." >> "$LOG_FILE"
        exit 1
    fi
else
    cd "$PROJECT_DIR"
    docker compose down
    docker compose up -d
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - [INFO] - Freqtrade upgraded successfully." >> "$LOG_FILE"
echo "Upgrade completed successfully."
