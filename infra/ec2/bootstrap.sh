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
# Registration/expiry notices for the public Let's Encrypt certificate.
CERTBOT_EMAIL="${CERTBOT_EMAIL:-tringuyenminh209@gmail.com}"

# Install the origin-facing TLS terminator and DNS-01 certificate tooling.
install_tls_proxy() {
  local policy_path="/usr/sbin/policy-rc.d"
  local policy_backup=""
  local suppress_nginx_autostart=0

  # On first install, keep nginx from claiming :80 while S1 Flexible traffic
  # may still be served by Docker. It starts after the TLS-only site is valid.
  if ! dpkg-query -W -f='${Status}' nginx 2>/dev/null \
    | grep -qx "install ok installed"; then
    if [[ -e "${policy_path}" ]]; then
      policy_backup="$(mktemp)"
      mv "${policy_path}" "${policy_backup}"
    fi
    printf '#!/bin/sh\nexit 101\n' > "${policy_path}"
    chmod 0755 "${policy_path}"
    suppress_nginx_autostart=1
  fi

  if ! apt-get install -y nginx certbot python3-certbot-dns-cloudflare; then
    if [[ "${suppress_nginx_autostart}" == "1" ]]; then
      if [[ -n "${policy_backup}" ]]; then
        mv "${policy_backup}" "${policy_path}"
      else
        rm -f "${policy_path}"
      fi
    fi
    return 1
  fi

  if [[ "${suppress_nginx_autostart}" == "1" ]]; then
    if [[ -n "${policy_backup}" ]]; then
      mv "${policy_backup}" "${policy_path}"
    else
      rm -f "${policy_path}"
    fi
  fi
}

# Issue/renew the public origin certificate using the operator-supplied token.
issue_origin_cert() {
  if [[ ! -f "${CF_DNS_CREDENTIALS_FILE}" ]]; then
    echo "Cloudflare DNS credentials not found at ${CF_DNS_CREDENTIALS_FILE}" >&2
    exit 1
  fi
  chmod 600 "${CF_DNS_CREDENTIALS_FILE}"
  certbot certonly \
    --dns-cloudflare \
    --dns-cloudflare-credentials "${CF_DNS_CREDENTIALS_FILE}" \
    --keep-until-expiring \
    -d "${ORIGIN_HOSTNAME}" \
    --non-interactive \
    --agree-tos \
    -m "${CERTBOT_EMAIL}"
  systemctl enable --now certbot.timer
  systemctl is-enabled certbot.timer
}

# Terminate TLS at nginx and keep the WebSocket audio bridge upgrade-capable.
configure_nginx_reverse_proxy() {
  local site_path="/etc/nginx/sites-available/lingoglass"
  local site_enabled="/etc/nginx/sites-enabled/lingoglass"
  local pending_site
  pending_site="$(mktemp)"
  cat > "${pending_site}" <<EOF
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${ORIGIN_HOSTNAME};

    ssl_certificate /etc/letsencrypt/live/${ORIGIN_HOSTNAME}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${ORIGIN_HOSTNAME}/privkey.pem;

    location / {
        proxy_pass http://${BACKEND_UPSTREAM};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
  if [[ ! -f "${site_path}" ]] || ! cmp -s "${pending_site}" "${site_path}"; then
    install -m 0644 "${pending_site}" "${site_path}"
  fi
  rm -f "${pending_site}"
  ln -sfn "${site_path}" "${site_enabled}"
  nginx -t
  systemctl enable --now nginx.service
  systemctl reload nginx.service
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
