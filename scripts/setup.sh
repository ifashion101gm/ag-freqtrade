#!/bin/bash
# ==============================================================================
# Freqtrade GCP Free Tier Deployment Setup & Hardening Script
# Author: Antigravity AI Assistant
# Description: Fully automated, idempotent server configuration, hardening,
#              Docker installation, Freqtrade setup, and service registration.
# Supported OS: Ubuntu 24.04 LTS (x86_64)
# Run as: root (or sudo)
# ==============================================================================

set -euo pipefail

# Define text formats
INFO='\033[0;36m'
SUCCESS='\033[0;32m'
WARNING='\033[0;33m'
ERROR='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${INFO}====================================================${NC}"
echo -e "${INFO} Starting Freqtrade Hardened VM Setup & Hardening    ${NC}"
echo -e "${INFO}====================================================${NC}"

# 1. Root User Check
if [ "$EUID" -ne 0 ]; then
    echo -e "${ERROR}Error: Please run this script as root or with sudo.${NC}"
    exit 1
fi

# Target installation directory
TARGET_DIR="/home/freqtrade/freqtrade-server"

# 2. Set Timezone to UTC
echo -e "${INFO}[1/10] Configuring Timezone to UTC...${NC}"
timedatectl set-timezone UTC
echo -e "${SUCCESS}Timezone set to $(date)${NC}"

# 3. Create Swap File (2GB)
echo -e "${INFO}[2/10] Setting up 2GB Swap File...${NC}"
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo -e "${SUCCESS}2GB Swap file created and enabled.${NC}"
else
    echo -e "${SUCCESS}Swap file already exists.${NC}"
fi

# 4. Update and Upgrade System Packages
echo -e "${INFO}[3/10] Updating and upgrading system packages...${NC}"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get upgrade -y
apt-get install -y \
    git \
    python3 \
    python3-pip \
    jq \
    curl \
    htop \
    tree \
    unattended-upgrades \
    fail2ban \
    chrony \
    ufw \
    logrotate \
    openssl

echo -e "${SUCCESS}System packages updated and utilities installed.${NC}"

# 5. Configure Automatic Updates (Hardening)
echo -e "${INFO}[4/10] Configuring Automatic Updates (unattended-upgrades)...${NC}"
echo "unattended-upgrades unattended-upgrades/enable_auto_updates boolean true" | debconf-set-selections
dpkg-reconfigure -f noninteractive unattended-upgrades
echo -e "${SUCCESS}Automatic security updates enabled.${NC}"

# 6. Configure fail2ban
echo -e "${INFO}[5/10] Configuring fail2ban for sshd...${NC}"
cat <<EOF > /etc/fail2ban/jail.local
[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 5
bantime = 1h
findtime = 10m
EOF
systemctl restart fail2ban
echo -e "${SUCCESS}fail2ban configured and restarted.${NC}"

# 7. Configure chrony
echo -e "${INFO}[6/10] Enabling and starting chrony NTP...${NC}"
systemctl enable chrony
systemctl start chrony
echo -e "${SUCCESS}chrony NTP sync active.${NC}"

# 8. Install Docker Engine & Compose Plugin
echo -e "${INFO}[7/10] Installing Docker and Docker Compose Plugin...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi
systemctl enable docker
systemctl start docker
echo -e "${SUCCESS}Docker installed and daemon enabled.${NC}"

# 9. Create Deployment User & Set Groups
echo -e "${INFO}[8/10] Creating deployment user 'freqtrade'...${NC}"
if ! id "freqtrade" &>/dev/null; then
    useradd -m -s /bin/bash freqtrade
    echo "freqtrade ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/freqtrade
    echo -e "${SUCCESS}User 'freqtrade' created with passwordless sudo permissions.${NC}"
else
    echo -e "${SUCCESS}User 'freqtrade' already exists.${NC}"
fi
usermod -aG docker freqtrade

# 10. SSH Hardening (Disable password auth, keep only keys)
echo -e "${INFO}[9/10] Hardening SSH access...${NC}"
cat <<EOF > /etc/ssh/sshd_config.d/hardening.conf
PasswordAuthentication no
PubkeyAuthentication yes
PermitRootLogin prohibit-password
ChallengeResponseAuthentication no
EOF
if systemctl is-active ssh &>/dev/null; then
    systemctl restart ssh
elif systemctl is-active sshd &>/dev/null; then
    systemctl restart sshd
fi
echo -e "${SUCCESS}SSH access hardened: passwords disabled, SSH keys required.${NC}"

# 11. Configure UFW Firewall
echo -e "${INFO}[10/10] Setting up UFW Firewall...${NC}"
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH Port'
ufw allow 80/tcp comment 'HTTP Nginx Proxy'
ufw allow 443/tcp comment 'HTTPS Nginx Proxy'
ufw --force enable
echo -e "${SUCCESS}UFW enabled: SSH (22), HTTP (80), and HTTPS (443) allowed.${NC}"

# 12. Deployment Directories & Files Setup
echo -e "${INFO}Setting up project structure and configurations in $TARGET_DIR...${NC}"
mkdir -p "$TARGET_DIR"

# Copy deployment files to target directory if script is run outside target
if [ "$(realpath "$PWD")" != "$(realpath "$TARGET_DIR")" ] && [ -f docker-compose.yml ]; then
    echo "Copying repository files from $PWD to $TARGET_DIR..."
    cp -r . "$TARGET_DIR/"
fi

# Ensure Freqtrade directory structure is created
mkdir -p "$TARGET_DIR/user_data/strategies" \
         "$TARGET_DIR/user_data/configs" \
         "$TARGET_DIR/user_data/logs" \
         "$TARGET_DIR/user_data/backtest" \
         "$TARGET_DIR/user_data/downloads" \
         "$TARGET_DIR/logs" \
         "$TARGET_DIR/backups" \
         "$TARGET_DIR/configs/certs" \
         "$TARGET_DIR/monitor"

# Generate Nginx Self-Signed Certificate if it doesn't exist
if [ ! -f "$TARGET_DIR/configs/certs/server.crt" ]; then
    echo "Generating self-signed SSL certificate for Nginx proxy..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout "$TARGET_DIR/configs/certs/server.key" \
      -out "$TARGET_DIR/configs/certs/server.crt" \
      -subj "/C=US/ST=State/L=City/O=Freqtrade/CN=localhost"
    chmod 600 "$TARGET_DIR/configs/certs/server.key"
fi

# Generate API Secrets in .env if it doesn't exist
if [ ! -f "$TARGET_DIR/.env" ]; then
    if [ -f "$TARGET_DIR/.env.example" ]; then
        cp "$TARGET_DIR/.env.example" "$TARGET_DIR/.env"
    else
        cat <<EOF > "$TARGET_DIR/.env"
API_USERNAME=admin
API_PASSWORD=ChooseAStrongPassword123!
JWT_SECRET_KEY=GenerateAStrongRandomKeyHere
EOF
    fi
    # Substitutions
    JWT_SECRET=$(openssl rand -hex 32)
    sed -i "s/GenerateAStrongRandomKeyHere/$JWT_SECRET/g" "$TARGET_DIR/.env"
    API_PASS=$(openssl rand -hex 16)
    sed -i "s/ChooseAStrongPassword123!/$API_PASS/g" "$TARGET_DIR/.env"
fi
chmod 600 "$TARGET_DIR/.env"

# 13. Systemd Service Integration for Freqtrade Lifecycle
echo -e "${INFO}Registering systemd service...${NC}"
cat <<EOF > /etc/systemd/system/freqtrade.service
[Unit]
Description=Freqtrade Docker Compose Service
Requires=docker.service
After=docker.service

[Service]
Type=simple
WorkingDirectory=$TARGET_DIR
ExecStartPre=-/usr/bin/docker compose down
ExecStart=/usr/bin/docker compose up
ExecStop=/usr/bin/docker compose down
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
User=freqtrade
Group=docker

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable freqtrade.service

# 14. Logrotate Configuration
echo -e "${INFO}Setting up log rotation configuration...${NC}"
cat <<EOF > /etc/logrotate.d/freqtrade
$TARGET_DIR/user_data/logs/*.log $TARGET_DIR/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
EOF

# 15. Correcting ownerships and permissions
echo -e "${INFO}Setting permissions and ownership to user 'freqtrade'...${NC}"
chown -R freqtrade:freqtrade "$TARGET_DIR"
find "$TARGET_DIR" -type f -name "*.sh" -exec chmod 700 {} \;

echo -e "${SUCCESS}====================================================${NC}"
echo -e "${SUCCESS} Setup completed successfully!                      ${NC}"
echo -e "${SUCCESS} To launch the bot, run:                             ${NC}"
echo -e "${SUCCESS}   sudo systemctl start freqtrade                   ${NC}"
echo -e "${SUCCESS} Monitor with:                                      ${NC}"
echo -e "${SUCCESS}   sudo journalctl -u freqtrade -f                  ${NC}"
echo -e "${SUCCESS}====================================================${NC}"
