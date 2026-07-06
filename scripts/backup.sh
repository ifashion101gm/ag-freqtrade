#!/bin/bash
# ==============================================================================
# Freqtrade Automated Backup Script
# Creates a compressed tarball of configuration, database, and strategies.
# Retains the last 7 backups to prevent disk depletion.
# ==============================================================================

set -euo pipefail

SCRIPTS_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_DIR="$(dirname "$SCRIPTS_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/freqtrade_backup_$TIMESTAMP.tar.gz"
LOG_FILE="$PROJECT_DIR/logs/backup.log"

mkdir -p "$BACKUP_DIR"
mkdir -p "$PROJECT_DIR/logs"

echo "$(date '+%Y-%m-%d %H:%M:%S') - [INFO] - Starting backup..." >> "$LOG_FILE"

DB_FILE="$PROJECT_DIR/user_data/tradesv3.sqlite"
TEMP_DB_BACKUP="/tmp/tradesv3_backup.sqlite"

# SQLite hot backup check
if [ -f "$DB_FILE" ]; then
    if command -v sqlite3 &>/dev/null; then
        sqlite3 "$DB_FILE" ".backup '$TEMP_DB_BACKUP'"
    else
        cp "$DB_FILE" "$TEMP_DB_BACKUP"
    fi
else
    TEMP_DB_BACKUP=""
fi

# Package files
if [ -n "$TEMP_DB_BACKUP" ] && [ -f "$TEMP_DB_BACKUP" ]; then
    STAGING_DIR="/tmp/freqtrade_staging_$TIMESTAMP"
    mkdir -p "$STAGING_DIR/user_data"
    cp -r "$PROJECT_DIR/configs" "$STAGING_DIR/"
    cp -r "$PROJECT_DIR/user_data/strategies" "$STAGING_DIR/user_data/"
    cp "$PROJECT_DIR/.env" "$STAGING_DIR/"
    cp "$TEMP_DB_BACKUP" "$STAGING_DIR/user_data/tradesv3.sqlite"
    
    tar -czf "$BACKUP_FILE" -C "$STAGING_DIR" configs user_data .env
    
    rm -rf "$STAGING_DIR"
    rm -f "$TEMP_DB_BACKUP"
else
    tar -czf "$BACKUP_FILE" -C "$PROJECT_DIR" configs user_data/strategies .env
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - [INFO] - Backup created: $(basename "$BACKUP_FILE")" >> "$LOG_FILE"

# Retention Policy: keep only last 7 backups
(cd "$BACKUP_DIR" && ls -tp freqtrade_backup_*.tar.gz 2>/dev/null | grep -v '/$' | tail -n +8 | xargs -I {} rm -- {} 2>/dev/null || true)

echo "$(date '+%Y-%m-%d %H:%M:%S') - [INFO] - Retention check completed." >> "$LOG_FILE"
