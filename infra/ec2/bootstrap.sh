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

# Print the facts operators need to confirm the machine is ready.
log "verification summary"
docker --version
docker compose version
ufw status verbose
id deploy
