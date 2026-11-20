#!/usr/bin/env bash
# Exercises deploy.sh and deploy-to-host.sh without Docker or a network: fake docker, curl and sleep
# on PATH, a throwaway deploy directory. Run from anywhere: deploy/test-deploy.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
WORK="$TMP/srv" FAKE="$TMP/fakes"
mkdir -p "$WORK" "$FAKE"
cp "$HERE/docker-compose.yml" "$WORK/"
printf 'IMAGE_PREFIX=ghcr.io/x\nPOSTGRES_PASSWORD=p\n' >"$WORK/.env"

cat >"$FAKE/docker" <<'SH'
#!/usr/bin/env bash
printf 'TAG=%s %s\n' "${TAG:-}" "$*" >>"$DOCKER_LOG"
if [[ "${FAIL_PULL:-0}" == 1 && " $* " == *" pull "* ]]; then exit 1; fi
exit 0
SH
# Healthy unless FAIL_URL names a substring of the URL being asked for (or FAIL_HEALTH=sqlite).
cat >"$FAKE/curl" <<'SH'
#!/usr/bin/env bash
url="${*: -1}"
if [[ -n "${FAIL_URL:-}" && "$url" == *"$FAIL_URL"* ]]; then exit 22; fi
if [[ "${FAIL_HEALTH:-}" == sqlite ]]; then printf '{"status":"ok","database":"sqlite"}'
else printf '{"status":"ok","database":"postgres"}'; fi
SH
printf '#!/usr/bin/env bash\nexit 0\n' >"$FAKE/sleep"
chmod +x "$FAKE"/*
export PATH="$FAKE:$PATH" ROOMLY_DEPLOY_DIR="$WORK" DOCKER_LOG="$TMP/docker.log"

failures=0
check() { # check <description> <actual> <expected>
  if [[ "$2" == "$3" ]]; then printf 'ok   %s\n' "$1"; else printf 'FAIL %s: got [%s] want [%s]\n' "$1" "$2" "$3"; failures=$((failures + 1)); fi
}
deploy() { SSH_ORIGINAL_COMMAND="$1" bash "$HERE/deploy.sh" >"$TMP/out" 2>&1 && echo 0 || echo $?; }
count() { grep -c -- "$1" "$DOCKER_LOG" || true; }
fresh() { printf '%s\n' "$1" >"$WORK/.current"; : >"$DOCKER_LOG"; }

for cmd in "" "deploy" "deploy main" "deploy v2" "deploy v2.2.0; id" "deploy v2.2.0 v2.3.0" "ls" "deploy v2.2.0
id"; do
  fresh v2.1.0
  check "refuses '${cmd//$'\n'/\\n}'" "$(deploy "$cmd")/$(wc -l <"$DOCKER_LOG" | tr -d ' ')/$(cat "$WORK/.current")" "1/0/v2.1.0"
done

fresh v2.1.0
check "deploys a new tag" "$(deploy 'deploy v2.2.0')/$(cat "$WORK/.current")" "0/v2.2.0"
check "pulls before it starts" "$(grep -Eo ' (pull|up) ' "$DOCKER_LOG" | tr -d ' \n')" "pullup"
check "passes the tag to compose" "$(count 'TAG=v2.2.0 ')" "2"

: >"$DOCKER_LOG"
check "same tag is a no-op" "$(deploy 'deploy v2.2.0')/$(wc -l <"$DOCKER_LOG" | tr -d ' ')" "0/0"

fresh v2.2.0
check "failed pull keeps the old tag" "$(FAIL_PULL=1 deploy 'deploy v2.3.0')/$(cat "$WORK/.current")" "1/v2.2.0"
check "failed pull restarts nothing" "$(count ' up ')" "0"

for broken in "8000/health" "3000/sign-in" "3000/api/health"; do
  fresh v2.2.0
  check "$broken down -> rolls back" "$(FAIL_URL=$broken deploy 'deploy v2.4.0')/$(cat "$WORK/.current")/$(count 'TAG=v2.2.0 .* up ')" "1/v2.2.0/1"
done
fresh v2.2.0
check "API on SQLite is unhealthy" "$(FAIL_HEALTH=sqlite deploy 'deploy v2.4.0')/$(cat "$WORK/.current")" "1/v2.2.0"

rm "$WORK/.current"; : >"$DOCKER_LOG"
check "first deploy failing has nothing to roll back to" "$(FAIL_URL=3000/sign-in deploy 'deploy v1.0.0')/$(count 'TAG=v1.0.0 .* up ')/$(test -e "$WORK/.current" && echo recorded || echo none)" "1/1/none"

for tag in "main; id" "v1" "v1.2.3 extra"; do
  rc=0; DEPLOY_HOST=h DEPLOY_USER=u DEPLOY_SSH_KEY=k DEPLOY_KNOWN_HOSTS=n bash "$HERE/deploy-to-host.sh" "$tag" >/dev/null 2>&1 || rc=$?
  check "deploy-to-host refuses '$tag'" "$rc" "2"
done

((failures == 0)) || { echo "$failures check(s) failed"; exit 1; }
echo "all checks passed"
