#!/bin/bash
# ==============================================================================
# Freqtrade Bot Health Monitor
# Checks system resources (Disk, Mem, CPU) and Freqtrade API ping endpoint.
# Auto-restarts services if unhealthy.
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
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [ERROR] - .env file not found." >> "$LOG_FILE"
    exit 1
fi

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
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [ERROR] - Freqtrade container is NOT running. Initiating restart..." >> "$LOG_FILE"
    "$MONITOR_DIR/restart.sh"
    exit 1
fi

# 3. Freqtrade API Health Check (Ping)
# Query local API server port 8080 directly
API_CHECK=$(curl -s -w "%{http_code}" -o /dev/null -u "$API_USERNAME:$API_PASSWORD" http://127.0.0.1:8080/api/v1/ping || echo "500")

if [ "$API_CHECK" -ne 200 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [ERROR] - Freqtrade API check failed (HTTP Code: $API_CHECK). Initiating restart..." >> "$LOG_FILE"
    "$MONITOR_DIR/restart.sh"
    exit 1
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [INFO] - Health Check Passed (Disk: ${DISK_USAGE}%, Mem: ${MEM_USAGE}%, CPU: ${CPU_USAGE}%, API: OK)" >> "$LOG_FILE"
fi
