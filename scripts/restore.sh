#!/bin/bash
# ==============================================================================
# Freqtrade System Recovery & Restore Script
# Restores configurations, strategies, and databases from a backup tarball.
# ==============================================================================

set -euo pipefail

SCRIPTS_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_DIR="$(dirname "$SCRIPTS_DIR")"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run this script with sudo/root permissions.${NC}"
    exit 1
fi

if [ "$#" -ne 1 ]; then
    echo -e "${YELLOW}Usage: sudo $0 <path_to_backup_tarball.tar.gz>${NC}"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}Error: Backup file '$BACKUP_FILE' not found.${NC}"
    exit 1
fi

echo -e "${YELLOW}Starting recovery process using backup: $BACKUP_FILE${NC}"

# 1. Stop Freqtrade service
echo "Stopping Freqtrade service..."
if systemctl list-unit-files | grep -q "^freqtrade.service"; then
    systemctl stop freqtrade.service || true
else
    cd "$PROJECT_DIR"
    docker compose down || true
fi

# 2. Extract backup
echo "Extracting backup archives to $PROJECT_DIR..."
tar -xzf "$BACKUP_FILE" -C "$PROJECT_DIR"

# 3. Fix ownerships and permissions
echo "Resetting ownership and permissions..."
chown -R freqtrade:freqtrade "$PROJECT_DIR"
find "$PROJECT_DIR" -type f -name "*.sh" -exec chmod 700 {} \;
chmod 600 "$PROJECT_DIR/.env"

# 4. Start Freqtrade service
echo "Restarting Freqtrade service..."
if systemctl list-unit-files | grep -q "^freqtrade.service"; then
    systemctl start freqtrade.service
else
    cd "$PROJECT_DIR"
    docker compose up -d
fi

echo -e "${GREEN}Recovery completed successfully!${NC}"
