#!/bin/bash
# ==============================================================================
# Freqtrade Bot Status Inspector
# Summarizes system resources, Docker container state, and queries Freqtrade
# API to show the active trading bot metrics.
# ==============================================================================

set -uo pipefail

MONITOR_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_DIR="$(dirname "$MONITOR_DIR")"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}=== Freqtrade Server Status ===${NC}"

# Load credentials
if [ -f "$PROJECT_DIR/.env" ]; then
    API_USERNAME=$(grep "^API_USERNAME=" "$PROJECT_DIR/.env" | cut -d'=' -f2 | xargs)
    API_PASSWORD=$(grep "^API_PASSWORD=" "$PROJECT_DIR/.env" | cut -d'=' -f2 | xargs)
else
    echo -e "${RED}[ERROR] .env file not found.${NC}"
    exit 1
fi

# 1. System Resource Overview
echo -e "\n${CYAN}1. System Resources:${NC}"
df -h / | awk 'NR==1 || NR==2 {print "  " $0}'
free -h | awk 'NR==1 || NR==2 || NR==3 {print "  " $0}'
echo "  CPU Load: $(top -bn1 | grep "Cpu(s)" | awk '{print 100 - $8}')%"

# 2. Docker Containers
echo -e "\n${CYAN}2. Docker Containers:${NC}"
if command -v docker &> /dev/null; then
    docker ps --filter "name=freqtrade" --filter "name=nginx" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | sed 's/^/  /'
else
    echo -e "  ${RED}Docker not installed/running${NC}"
fi

# 3. Freqtrade Bot REST API Metrics
echo -e "\n${CYAN}3. Freqtrade Bot API Info:${NC}"
PING_STATUS=$(curl -s -u "$API_USERNAME:$API_PASSWORD" http://127.0.0.1:8080/api/v1/ping || echo "offline")

if [ "$PING_STATUS" = "offline" ]; then
    echo -e "  Status: ${RED}OFFLINE / UNRESPONSIVE${NC}"
else
    # Query Freqtrade REST API status endpoints
    BOT_STATE=$(curl -s -u "$API_USERNAME:$API_PASSWORD" http://127.0.0.1:8080/api/v1/status | jq -r '.status' 2>/dev/null || echo "Unknown")
    VERSION=$(curl -s -u "$API_USERNAME:$API_PASSWORD" http://127.0.0.1:8080/api/v1/version | jq -r '.version' 2>/dev/null || echo "Unknown")
    PROFIT=$(curl -s -u "$API_USERNAME:$API_PASSWORD" http://127.0.0.1:8080/api/v1/profit | jq -r '.profit_percent' 2>/dev/null || echo "0")
    
    echo -e "  API Ping:     ${GREEN}Online${NC}"
    echo -e "  Bot Version:  ${YELLOW}${VERSION}${NC}"
    echo -e "  Bot State:    ${GREEN}${BOT_STATE}${NC}"
    echo -e "  Total Profit: ${YELLOW}${PROFIT}%${NC}"
fi

# 4. Recent Freqtrade Logs
echo -e "\n${CYAN}4. Recent Logs (Last 10 lines):${NC}"
if [ -d "$PROJECT_DIR/user_data/logs" ]; then
    # Find latest log file
    LATEST_LOG=$(find "$PROJECT_DIR/user_data/logs" -type f -name "*.log" -o -name "*.json" | sort -V | tail -n 1)
    if [ -n "$LATEST_LOG" ]; then
        echo -e "  Log file: $(basename "$LATEST_LOG")"
        tail -n 10 "$LATEST_LOG" | sed 's/^/  /'
    else
        echo -e "  No log files found in user_data/logs."
    fi
else
    echo -e "  Logs directory does not exist."
fi
