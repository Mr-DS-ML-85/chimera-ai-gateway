# Chimera Gateway Security Stack

Comprehensive security stack combining **CrowdSec** and **Fail2Ban** to protect the Chimera Gateway from brute force attacks, scanners, and abuse.

## Architecture

```
                                    ┌─────────────┐
                                    │   CrowdSec  │ ← Community threat intelligence
                                    │   Firewall  │
                                    │   Bouncer   │ ← Applies iptables bans
                                    └──────┬──────┘
                                           │
Internet ──────► Port 80/443 ──► Nginx ──► Gateway:8000
                        │          │              │
                        │          │              └── Fail2Ban ← Pattern detection
                        │          │
                        └──────────┘
                              │
                        CrowdSec ← Log parsing & threat detection
```

## Services

| Service | Image | Purpose |
|---------|-------|---------|
| `nginx` | nginx:1.25-alpine | Reverse proxy, rate limiting, SSL termination |
| `gateway` | chimera_gateway:latest | Main application server |
| `redis` | redis:7-alpine | Session store |
| `crowdsec` | crowdsec/crowdsec:v1.5.4 | Community threat intelligence, log parsing |
| `crowdsec-firewall-bouncer` | crowdsecurity/firewall-bouncer | Applies CrowdSec ban decisions |
| `fail2ban` | crazymax/fail2ban:latest | Pattern-based abuse detection |

## Quick Start

### 1. Initial Setup

```bash
# Make setup script executable
chmod +x setup-security.sh

# Run setup (generates SSL certs and credentials)
./setup-security.sh
```

### 2. Start Services

```bash
# Start with existing docker-compose
docker compose -f docker-compose.yml -f docker-compose.security.yml up -d

# Or start security stack only
docker compose -f docker-compose.security.yml up -d
```

### 3. Verify Status

```bash
# Check CrowdSec decisions
docker exec chimera_crowdsec cscli decisions list

# Check Fail2Ban status
docker exec chimera_fail2ban fail2ban-client status

# View nginx logs
docker logs chimera_nginx
```

## Port Configuration

| Port | Service | Description |
|------|---------|-------------|
| 80 | Nginx | HTTP reverse proxy |
| 443 | Nginx | HTTPS (self-signed cert) |
| 8000 | Gateway | Direct access (testing only) |
| 6060 | CrowdSec | Local API |
| 9090 | Fail2Ban | Web UI (optional) |

## Configuration Files

```
configs/
├── nginx/
│   └── nginx.conf          # Reverse proxy, rate limiting, SSL
├── crowdsec/
│   ├── acquis.yaml         # Log sources to monitor
│   ├── profiles.yaml       # Ban thresholds and decisions
│   ├── crowdsec.yaml       # Main CrowdSec config
│   ├── firewall-bouncer.yaml
│   └── .env                # API credentials
└── fail2ban/
    ├── jail.local          # Jails and actions
    ├── fail2ban.conf       # Base configuration
    ├── filter.d/           # Custom filters
    │   ├── chimera-auth.conf
    │   ├── nginx-bad-bot.conf
    │   └── http-get-dos.conf
    └── action.d/           # Custom actions
```

## Detections

### CrowdSec

- **HTTP Scanner**: Detects aggressive web crawlers (>50 req/min)
- **HTTP Crawler**: Detects moderate scraping (30-50 req/min)
- **SQL Injection**: Blocks SQL injection attempts
- **HTTP Probing**: Detects scanning of sensitive paths
- **Brute Force**: Detects auth brute force attacks
- **Community Blocklist**: Uses community-driven threat intelligence

### Fail2Ban

- **nginx-http-auth**: HTTP auth failures
- **nginx-bad-bot**: Malicious user-agents
- **nginx-404**: Excessive 404s (possible scanning)
- **http-get-dos**: GET flood detection
- **http-post-dos**: POST flood detection
- **chimera-auth**: Chimera-specific auth failures
- **sshd**: SSH brute force protection

## Managing Bans

### CrowdSec

```bash
# View active bans
docker exec chimera_crowdsec cscli decisions list

# Ban an IP manually
docker exec chimera_crowdsec cscli decisions add -i 1.2.3.4 -t ban -d 24h

# Unban an IP
docker exec chimera_crowdsec cscli decisions delete -i 1.2.3.4

# View banned countries
docker exec chimera_crowdsec cscli decisions list -t ban -c

# View ban history
docker exec chimera_crowdsec cscli decisions list -o table
```

### Fail2Ban

```bash
# View jail status
docker exec chimera_fail2ban fail2ban-client status

# View specific jail bans
docker exec chimera_fail2ban fail2ban-client status chimera-auth

# Unban an IP
docker exec chimera_fail2ban fail2ban-client set chimera-auth unbanip 1.2.3.4

# View fail2ban log
docker exec chimera_fail2ban cat /var/log/fail2ban/fail2ban.log
```

## Customization

### Adjust Detection Thresholds

Edit `configs/crowdsec/profiles.yaml` for CrowdSec sensitivity:

```yaml
- name: http_scanner
  filters:
    - 'evt.Meta.service == "nginx"'
    - 'evt.Meta.value >= 50'  # Increase for more tolerance
  decisions:
    - type: ban
      duration: 8h
```

Edit `configs/fail2ban/jail.local` for Fail2Ban sensitivity:

```ini
[http-get-dos]
enabled = true
maxretry = 50        # Increase for more tolerance
findtime = 30        # Time window in seconds
bantime = 600        # Ban duration
```

### Add Custom Filters

Create new filters in `configs/fail2ban/filter.d/`:

```bash
# Example: Custom API abuse detection
# configs/fail2ban/filter.d/api-abuse.conf
[Definition]
failregex = ^<HOST> - - \[.*?\] "GET /api/.*" (401|403) [0-9]+
ignoreregex =
```

### Update Community Blocklists

```bash
# Update CrowdSec hub
docker exec chimera_crowdsec cscli hub update

# Install additional scenarios
docker exec chimera_crowdsec cscli collections install crowdsecurity/http-crawl-non_statics

# View installed scenarios
docker exec chimera_crowdsec cscli scenarios list
```

## Troubleshooting

### Services not starting

```bash
# Check logs
docker compose -f docker-compose.security.yml logs crowdsec
docker compose -f docker-compose.security.yml logs fail2ban

# Verify network connectivity
docker exec chimera_crowdsec ping gateway
```

### Bounces not working

```bash
# Check if bouncer can reach API
docker exec chimera_crowdsec_bouncer cscli bouncer list

# Verify API key
docker exec chimera_crowdsec cscli bouncer list
```

### Logs not parsing

```bash
# Test CrowdSec log parsing
docker exec chimera_crowdsec cscli log analyze

# Check acquisition status
docker exec chimera_crowdsec cscli metrics
```

## Production Recommendations

1. **Use proper SSL certificates** (Let's Encrypt)
2. **Configure external Redis** for session sharing
3. **Set up log rotation** for nginx logs
4. **Enable CrowdSec dashboard** for monitoring
5. **Whitelist known IPs** (load balancers, internal networks)
6. **Monitor ban rates** and adjust thresholds
7. **Consider adding WAF** (ModSecurity) for additional protection

## Stopping Services

```bash
# Stop security stack
docker compose -f docker-compose.yml -f docker-compose.security.yml down

# Stop and remove volumes
docker compose -f docker-compose.yml -f docker-compose.security.yml down -v
```