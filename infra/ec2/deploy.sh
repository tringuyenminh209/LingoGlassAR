#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  echo "deploy.sh must run as the deploy user, not root. Use: sudo -u deploy -i" >&2
  exit 1
fi

REPO_DIR="/home/deploy/lingoglass"
BACKEND_DIR="/home/deploy/lingoglass/backend"

log() {
  printf '[deploy %s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1"
}

log "sync main from origin"
cd "${REPO_DIR}"
git fetch origin --prune
git checkout main
git pull --ff-only origin main

log "validate backend environment"
cd "${BACKEND_DIR}"
if [[ ! -f /home/deploy/lingoglass/backend/.env ]]; then
  echo "Missing /home/deploy/lingoglass/backend/.env. See docs/runbook/aws-osaka-deploy.md section 'First deploy'." >&2
  exit 1
fi

log "pull available Compose images"
docker compose pull --quiet

log "build and start backend stack"
docker compose up -d --build --remove-orphans

log "wait for api container healthcheck"
api_container="$(docker compose ps -q api)"
if [[ -z "${api_container}" ]]; then
  echo "Could not find api container after docker compose up." >&2
  docker compose logs api --tail 60 >&2
  exit 1
fi

deadline=$((SECONDS + 60))
while (( SECONDS < deadline )); do
  health_status="$(docker inspect --format '{{.State.Health.Status}}' "${api_container}" 2>/dev/null || true)"
  if [[ "${health_status}" == "healthy" ]]; then
    log "api container is healthy"
    break
  fi
  sleep 2
done

if [[ "${health_status:-}" != "healthy" ]]; then
  echo "api container did not become healthy within 60 seconds; last status: ${health_status:-unknown}" >&2
  docker compose logs api --tail 60 >&2
  exit 1
fi

log "verify local health endpoint"
# Discover the published host port from docker compose, not the hard-coded
# 8000, so the script works when API_HOST_PORT in .env is 80 (Cloudflare prod).
published="$(docker compose port api 8000 2>/dev/null || true)"
host_port="${published##*:}"
host_port="${host_port:-8000}"
curl -fsS "http://localhost:${host_port}/healthz"
printf '\n'
