#!/bin/bash
# ==============================================================================
# Freqtrade Bot Health Monitor – D3 Vantage Bot
# Checks system resources (Disk, Mem, CPU) and Freqtrade API ping endpoint.
# Auto-restarts services if unhealthy + sends Telegram alert.
# ==============================================================================

set -uo pipefail

MONITOR_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_DIR="$(dirname "$MONITOR_DIR")"
LOG_FILE="$PROJECT_DIR/logs/health.log"

mkdir -p "$PROJECT_DIR/logs"

# Load values from .env
if [ -f "$PROJECT_DIR/.env" ]; then
    API_USERNAME=$(grep "^API_USERNAME=" "$PROJECT_DIR/.env" | cut -d'=' -f2 | xargs)
    API_PASSWORD=$(grep "^API_PASSWORD=" "$PROJECT_DIR/.env" | cut -d'=' -f2 | xargs)
    TG_TOKEN=$(grep "^TELEGRAM_BOT_TOKEN=" "$PROJECT_DIR/.env" | cut -d'=' -f2 | xargs)
    TG_CHAT_ID=$(grep "^TELEGRAM_CHAT_ID=" "$PROJECT_DIR/.env" | cut -d'=' -f2 | xargs)
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [ERROR] - .env file not found." >> "$LOG_FILE"
    exit 1
fi

# ─── Telegram helper ─────────────────────────────────────────────────────────
telegram_alert() {
    local msg="$1"
    if [ -n "${TG_TOKEN:-}" ] && [ -n "${TG_CHAT_ID:-}" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
            -d chat_id="${TG_CHAT_ID}" \
            -d text="${msg}" \
            -d parse_mode="Markdown" > /dev/null 2>&1 || true
    fi
}


# Thresholds
DISK_LIMIT=90
MEM_LIMIT=95
CPU_LIMIT=95

# 1. System Checks
# Disk
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt "$DISK_LIMIT" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [WARN] - High Disk Usage: ${DISK_USAGE}%" >> "$LOG_FILE"
fi

# Memory
MEM_USAGE=$(free | grep Mem | awk '{print int($3/$2 * 100)}')
if [ "$MEM_USAGE" -gt "$MEM_LIMIT" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [WARN] - High Memory Usage: ${MEM_USAGE}%" >> "$LOG_FILE"
fi

# CPU
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}' | cut -d. -f1)
if [ "$CPU_USAGE" -gt "$CPU_LIMIT" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [WARN] - High CPU Usage: ${CPU_USAGE}%" >> "$LOG_FILE"
fi

# 2. Freqtrade Docker Status
CONTAINER_STATUS=$(docker inspect -f '{{.State.Running}}' freqtrade 2>/dev/null || echo "false")
if [ "$CONTAINER_STATUS" != "true" ]; then
    MSG="\ud83d\udd01 *D3 Bot RESTART*\nFreqtrade container was NOT running.\nHost: $(hostname)\nTime: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [ERROR] - Freqtrade container is NOT running. Initiating restart..." >> "$LOG_FILE"
    telegram_alert "$MSG"
    "$MONITOR_DIR/restart.sh"
    exit 1
fi

# 3. Freqtrade API Health Check (Ping)
# Query local API server port 8080 directly
API_CHECK=$(curl -s -w "%{http_code}" -o /dev/null -u "$API_USERNAME:$API_PASSWORD" http://127.0.0.1:8080/api/v1/ping || echo "500")

if [ "$API_CHECK" -ne 200 ]; then
    MSG="\ud83d\udea8 *D3 Bot API FAIL*\nFreqtrade API returned HTTP $API_CHECK.\nInitiating restart...\nHost: $(hostname)"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [ERROR] - Freqtrade API check failed (HTTP Code: $API_CHECK). Initiating restart..." >> "$LOG_FILE"
    telegram_alert "$MSG"
    "$MONITOR_DIR/restart.sh"
    exit 1
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [INFO] - Health Check Passed (Disk: ${DISK_USAGE}%, Mem: ${MEM_USAGE}%, CPU: ${CPU_USAGE}%, API: OK)" >> "$LOG_FILE"
fi
