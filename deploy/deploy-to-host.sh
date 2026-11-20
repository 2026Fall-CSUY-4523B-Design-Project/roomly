#!/usr/bin/env bash
# Ask the host to deploy one tag. Runs on the CI runner; the ssh key holds no shell.
# Usage: deploy/deploy-to-host.sh v2.2.0
set -euo pipefail

TAG="${1:-}"
if [[ ! "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.]+)?$ ]]; then
  echo "deploy: usage: deploy/deploy-to-host.sh v2.2.0" >&2
  exit 2
fi

: "${DEPLOY_HOST:?DEPLOY_HOST is not set}"
: "${DEPLOY_USER:?DEPLOY_USER is not set}"
: "${DEPLOY_SSH_KEY:?DEPLOY_SSH_KEY is not set}"
: "${DEPLOY_KNOWN_HOSTS:?DEPLOY_KNOWN_HOSTS is not set}"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

printf '%s\n' "$DEPLOY_SSH_KEY" >"$tmp/key"
chmod 600 "$tmp/key"
printf '%s\n' "$DEPLOY_KNOWN_HOSTS" >"$tmp/known_hosts"

echo "deploy: asking $DEPLOY_USER@$DEPLOY_HOST for $TAG"
exec ssh -i "$tmp/key" \
  -o IdentitiesOnly=yes \
  -o BatchMode=yes \
  -o StrictHostKeyChecking=yes \
  -o "UserKnownHostsFile=$tmp/known_hosts" \
  -o ConnectTimeout=15 \
  -o ServerAliveInterval=15 \
  "$DEPLOY_USER@$DEPLOY_HOST" "deploy $TAG"
