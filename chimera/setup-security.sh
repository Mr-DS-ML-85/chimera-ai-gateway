#!/bin/bash
# Chimera Gateway Security Stack Setup Script
# Run this to initialize the security services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================="
echo "Chimera Security Stack Setup"
echo "=================================="

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed"
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker compose &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed"
    exit 1
fi

# Generate SSL self-signed certificate if not exists
SSL_DIR="$SCRIPT_DIR/configs/nginx/ssl"
mkdir -p "$SSL_DIR"

if [ ! -f "$SSL_DIR/server.crt" ]; then
    echo "Generating self-signed SSL certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$SSL_DIR/server.key" \
        -out "$SSL_DIR/server.crt" \
        -subj "/C=US/ST=State/L=City/O=Chimera/CN=chimera.local" \
        2>/dev/null
    echo "SSL certificate generated."
fi

# Create fail2ban configuration directory structure
mkdir -p "$SCRIPT_DIR/configs/fail2ban/action.d"
mkdir -p "$SCRIPT_DIR/configs/fail2ban/filter.d"

# Copy default fail2ban configs if not exists
if [ ! -f "$SCRIPT_DIR/configs/fail2ban/fail2ban.conf" ]; then
    echo "Creating fail2ban base configuration..."
    cat > "$SCRIPT_DIR/configs/fail2ban/fail2ban.conf" << 'EOF'
[Definition]
loglevel = INFO
logtarget = STDOUT
socket = /var/run/fail2ban/fail2ban.sock
pidfile = /var/run/fail2ban/fail2ban.pid
dbfile = /var/lib/fail2ban/fail2ban.db
dbpurgeage = 86400
EOF
fi

# Create CrowdSec API key (generate and update .env)
echo "Generating CrowdSec bouncer API key..."

# Generate a random password for Local API
LOCAL_API_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
CROWDSEC_API_KEY=$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)

# Update .env file
cat > "$SCRIPT_DIR/configs/crowdsec/.env" << EOF
# CrowdSec Environment Variables
# Generated on: $(date)
CROWDSEC_LOCAL_API_PASSWORD=$LOCAL_API_PASS
CROWDSEC_API_KEY=$CROWDSEC_API_KEY
TZ=UTC
EOF

echo "Environment file updated with secure credentials."

# Pull Docker images
echo ""
echo "Pulling Docker images..."
docker pull nginx:1.25-alpine
docker pull crowdsec/crowdsec:v1.5.4
docker pull crowdsecurity/firewall-bouncer:latest
docker pull crazymax/fail2ban:latest

echo ""
echo "=================================="
echo "Setup complete!"
echo "=================================="
echo ""
echo "To start the security stack:"
echo "  docker compose -f docker-compose.yml -f docker-compose.security.yml up -d"
echo ""
echo "To view CrowdSec decisions:"
echo "  docker exec chimera_crowdsec cscli decisions list"
echo ""
echo "To view Fail2Ban status:"
echo "  docker exec chimera_fail2ban fail2ban-client status"
echo ""
echo "To generate a new API key for bouncers:"
echo "  docker exec chimera_crowdsec cscli bouncer add <name>"
echo ""
echo "Configuration files are in:"
echo "  - configs/nginx/nginx.conf"
echo "  - configs/crowdsec/*.yaml"
echo "  - configs/fail2ban/jail.local"
echo ""