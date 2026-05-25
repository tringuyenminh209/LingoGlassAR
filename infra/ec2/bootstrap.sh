#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "bootstrap.sh must be run as root: sudo bash /tmp/bootstrap.sh" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

log() {
  printf '[bootstrap %s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1"
}

# Keep package metadata and security patches current before installing services.
log "refresh apt metadata and apply security updates"
apt-get update -y
apt-get upgrade -y

# Install only the OS tools needed for Docker, firewalling, and git deploys.
log "install base packages required for Docker, firewall, and git deploys"
apt-get install -y ca-certificates curl gnupg lsb-release ufw git

# Use Docker's official arm64 repository instead of Ubuntu's docker.io package.
log "configure the official Docker apt repository for arm64 packages"
architecture="$(dpkg --print-architecture)"
if [[ "${architecture}" != "arm64" ]]; then
  echo "Unsupported architecture '${architecture}'; expected arm64 for Osaka t4g instances." >&2
  exit 1
fi

install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
fi

docker_repo_line="deb [arch=arm64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && printf '%s' "${VERSION_CODENAME}") stable"
if [[ ! -f /etc/apt/sources.list.d/docker.list ]] \
  || [[ "$(cat /etc/apt/sources.list.d/docker.list)" != "${docker_repo_line}" ]]; then
  printf '%s\n' "${docker_repo_line}" > /etc/apt/sources.list.d/docker.list
fi

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# The deploy user owns the checkout and can run Docker without sudo.
log "create the deploy user and grant Docker group access"
if ! id deploy >/dev/null 2>&1; then
  useradd --create-home --home-dir /home/deploy --shell /bin/bash --groups docker deploy
fi
if ! id -nG deploy | tr ' ' '\n' | grep -qx docker; then
  usermod --append --groups docker deploy
fi

# The runbook clones into this stable path after bootstrap completes.
log "prepare the repository checkout directory without cloning"
install -d -o deploy -g deploy -m 0755 /home/deploy/lingoglass

# Limit public ingress to SSH and Cloudflare-facing HTTP/HTTPS.
log "enable ufw with only SSH, HTTP, and HTTPS ingress"
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Ensure the backend stack can start now and after instance reboot.
log "enable and start Docker service"
systemctl enable docker.service
systemctl start docker.service

# --- S2 Day 7: origin TLS reverse-proxy for Cloudflare Full(Strict) ---
#
# Default OFF: an unset/0 LINGOGLASS_TLS_PROXY leaves the S1 Flexible setup
# (Cloudflare -> origin HTTP on :80) completely unchanged, so re-running
# this script on the existing box is still idempotent and non-destructive.
#
# Set LINGOGLASS_TLS_PROXY=1 (plus the CF_* vars below) to provision nginx
# as a TLS-terminating reverse proxy in front of the backend container and
# obtain a Let's Encrypt origin certificate. The cert is issued via the
# DNS-01 challenge, NOT HTTP-01: the `api` record is orange-clouded
# (proxied), so an HTTP-01 challenge would be answered by Cloudflare's edge
# instead of this origin and would fail. DNS-01 proves control via a
# Cloudflare API token and is unaffected by the proxy. See
# docs/runbook/cloudflare-tls.md for the cert-path trade-off and the manual
# step list.
TLS_PROXY_ENABLED="${LINGOGLASS_TLS_PROXY:-0}"
# Public hostname the origin cert is issued for.
ORIGIN_HOSTNAME="${ORIGIN_HOSTNAME:-api.lingoglass.online}"
# certbot dns-cloudflare credentials file (ini with a scoped API token).
# Must be created out-of-band by the operator; never committed.
CF_DNS_CREDENTIALS_FILE="${CF_DNS_CREDENTIALS_FILE:-/home/deploy/.secrets/cf-dns.ini}"
# Where nginx forwards decrypted traffic. The backend must bind here
# (127.0.0.1:8000) instead of the public :80 once the proxy owns 80/443 —
# that compose/.env change is part of the Day 8 migration, see runbook.
BACKEND_UPSTREAM="${BACKEND_UPSTREAM:-127.0.0.1:8000}"

# TODO(codex, S2 Day 7): install nginx + certbot + the dns-cloudflare plugin.
install_tls_proxy() {
  : # apt-get install -y nginx certbot python3-certbot-dns-cloudflare
}

# TODO(codex, S2 Day 7): issue the origin cert via DNS-01 and confirm the
# auto-renew timer. certbot installs/enables certbot.timer itself; verify it
# with `systemctl is-enabled certbot.timer`. Use --non-interactive and a
# real --email; chmod 600 the credentials file before calling certbot.
issue_origin_cert() {
  : # certbot certonly --dns-cloudflare \
    #   --dns-cloudflare-credentials "${CF_DNS_CREDENTIALS_FILE}" \
    #   -d "${ORIGIN_HOSTNAME}" --non-interactive --agree-tos -m <email>
}

# TODO(codex, S2 Day 7): write /etc/nginx/sites-available/lingoglass:
#   server { listen 443 ssl http2; server_name ${ORIGIN_HOSTNAME};
#     ssl_certificate     /etc/letsencrypt/live/${ORIGIN_HOSTNAME}/fullchain.pem;
#     ssl_certificate_key /etc/letsencrypt/live/${ORIGIN_HOSTNAME}/privkey.pem;
#     location / { proxy_pass http://${BACKEND_UPSTREAM};
#       # WS upgrade is required — the mobile app streams audio over wss.
#       proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade;
#       proxy_set_header Connection "upgrade"; proxy_set_header Host $host;
#       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
#       proxy_set_header X-Forwarded-Proto $scheme; } }
# Optional :80 server block returning 301 to https (Cloudflare hits :443).
# Then: enable the site, `nginx -t`, `systemctl reload nginx`.
configure_nginx_reverse_proxy() {
  : # see TODO above
}

if [[ "${TLS_PROXY_ENABLED}" == "1" ]]; then
  log "provision origin TLS reverse-proxy (Cloudflare Full(Strict)) for ${ORIGIN_HOSTNAME}"
  install_tls_proxy
  issue_origin_cert
  configure_nginx_reverse_proxy
else
  log "skip origin TLS proxy (LINGOGLASS_TLS_PROXY != 1); origin stays HTTP-only on :80"
fi

# Print the facts operators need to confirm the machine is ready.
log "verification summary"
docker --version
docker compose version
ufw status verbose
id deploy
