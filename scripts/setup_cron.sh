#!/bin/bash
# ==============================================================================
# setup_cron.sh – Install D3 Bot Cron Jobs
# Run once on the GCP VM to set up automated monitoring and backups.
# ==============================================================================
# Usage: bash scripts/setup_cron.sh

set -euo pipefail

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo " D3 Bot – Cron Setup"
echo " Project dir: $PROJECT_DIR"
echo "========================================"

# ─── Make all scripts executable ─────────────────────────────────────────────
chmod +x "$PROJECT_DIR/monitor/health.sh"
chmod +x "$PROJECT_DIR/monitor/restart.sh" 2>/dev/null || true
chmod +x "$PROJECT_DIR/monitor/status.sh"  2>/dev/null || true
chmod +x "$PROJECT_DIR/scripts/backup.sh"  2>/dev/null || true
chmod +x "$PROJECT_DIR/scripts/restore.sh" 2>/dev/null || true
echo "[OK] Scripts made executable"

# ─── Build crontab entries ────────────────────────────────────────────────────
CRON_HEALTH="*/5 * * * * $PROJECT_DIR/monitor/health.sh >> $PROJECT_DIR/logs/health_cron.log 2>&1"
CRON_BACKUP="0 2 * * * $PROJECT_DIR/scripts/backup.sh >> $PROJECT_DIR/logs/backup.log 2>&1"
CRON_RESET="59 23 * * * echo '{}' > $PROJECT_DIR/user_data/logs/prop_firm_state.json"

# Install cron jobs (skip if already present)
install_cron() {
    local entry="$1"
    local label="$2"
    if crontab -l 2>/dev/null | grep -qF "${entry%%>*}"; then
        echo "[SKIP] Already installed: $label"
    else
        (crontab -l 2>/dev/null; echo "$entry") | crontab -
        echo "[OK]   Installed: $label"
    fi
}

install_cron "$CRON_HEALTH" "Health check every 5 min"
install_cron "$CRON_BACKUP" "Daily backup at 2am UTC"
install_cron "$CRON_RESET"  "Prop Firm state reset at 23:59 UTC"

echo ""
echo "Current crontab:"
crontab -l
echo ""
echo "[DONE] Cron jobs installed."
echo ""
echo "To verify health check runs:"
echo "  bash $PROJECT_DIR/monitor/health.sh"
echo ""
echo "To view logs:"
echo "  tail -f $PROJECT_DIR/logs/health.log"
echo "  tail -f $PROJECT_DIR/logs/d3_bot.jsonl"
