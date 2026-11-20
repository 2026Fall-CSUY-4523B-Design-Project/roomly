#!/usr/bin/env bash
# Forced command for the deploy key:
#
#   /srv/roomly/deploy.sh        (root-owned, 0755; referenced from authorized_keys)
#   ssh roomly-deploy@host 'deploy v2.2.0'
#
# The key can do exactly one thing: pull one public image tag and restart the stack. It cannot read
# files, start a shell or run anything else, so a leaked key is worth no more than a tag push.
set -euo pipefail

readonly DIR="${ROOMLY_DEPLOY_DIR:-/srv/roomly}"
readonly USAGE='usage: deploy v<major>.<minor>.<patch>[-suffix]'

log() { printf '[deploy] %s\n' "$*"; }
die() { printf '[deploy] %s\n' "$*" >&2; exit 1; }

[[ "${SSH_ORIGINAL_COMMAND:-}" =~ ^deploy\ (v[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.]+)?)$ ]] || die "$USAGE"
tag="${BASH_REMATCH[1]}"

cd "$DIR"
previous="$(cat .current 2>/dev/null || true)"

if [[ "$tag" == "$previous" ]]; then
  log "$tag is already deployed"
  exit 0
fi

run() { TAG="$tag" IMAGE_PREFIX="${IMAGE_PREFIX:-ghcr.io/2026fall-csuy-4523b-design-project}" \
        docker compose --env-file .env -f docker-compose.yml "$@"; }

log "pulling $tag"
run pull --quiet || die "pull failed for $tag; nothing was restarted"

log "starting $tag"
run up -d --remove-orphans || die "compose up failed for $tag"

# Through the frontend as well as the API: a broken /api rewrite must fail the deploy, not the users.
healthy() {
  curl -fsS --max-time 3 http://127.0.0.1:8000/health \
    | grep -Eq '"database"[[:space:]]*:[[:space:]]*"postgres"' &&
  curl -fsS --max-time 3 -o /dev/null http://127.0.0.1:3000/sign-in &&
  curl -fsS --max-time 3 http://127.0.0.1:3000/api/health \
    | grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"'
}

ok=0
for _ in $(seq 1 30); do
  if healthy; then ok=1; break; fi
  sleep 1
done

if [[ "$ok" -ne 1 ]]; then
  log "$tag did not become healthy in 30s"
  if [[ -n "$previous" ]]; then
    log "rolling back to $previous"
    TAG="$previous" IMAGE_PREFIX="${IMAGE_PREFIX:-ghcr.io/2026fall-csuy-4523b-design-project}" \
      docker compose --env-file .env -f docker-compose.yml up -d --remove-orphans || true
    for _ in $(seq 1 20); do
      if healthy; then log "back on $previous"; break; fi
      sleep 1
    done
  else
    log "no previous release to roll back to"
  fi
  exit 1
fi

echo "$tag" >.current
log "$tag is live"
