# Deployment

```
tag v* ──> GitHub Actions
              tests → build api + web images → push ghcr.io/…/roomly-{api,web}:<tag>
              → deploy the mail Worker → ssh 'deploy <tag>'
                                                  │
Cloudflare (DNS, edge TLS, mail) ──┐              ▼
                                   │   RackNerd VPS: docker compose
      roomly.bid ──────────────────┴──> nginx :443 → web :3000 → api :8000 → db
      mail.roomly.bid ─────────────────> roomly-mail Worker
```

Four moving parts and nothing else: two images in a public registry, one compose file, one nginx
site, one Worker.

| Workflow | Trigger | What it does |
| --- | --- | --- |
| `ci.yml` | PR, push to `main` | lint, backend tests on Postgres, frontend build, and both images built (not pushed) |
| `release.yml` | `v*` tag | tests, push both images to ghcr, deploy the mail Worker, deploy the host, open the GitHub Release |
| `mail.yml` | PR or push touching `mail/` | typecheck, vitest, `wrangler deploy --dry-run`; `main` deploys the staging Worker |

A tag deploys without an approval step. That is deliberate, and it means **whoever can push a `v*`
tag can put code in production**. The defence is therefore not the pipeline but the container: the
API runs as an unprivileged user in a read-only container and cannot reach the host, the deploy key
or any credential except its own environment.

## On the host

```
/srv/roomly/
  docker-compose.yml     root, 0644
  .env                   root:roomly-deploy, 0640 — secrets, never the tag
  .current               the tag that passed its health check
  deploy.sh              root, 0755 — the only thing the deploy key may run
```

Compose starts three services:

| Service | Notes |
| --- | --- |
| `api` | image `roomly-api:<tag>`; `read_only`, `cap_drop: ALL`, `no-new-privileges`, non-root uid 10001, listens on `127.0.0.1:8000` only |
| `web` | image `roomly-web:<tag>`; same hardening; `127.0.0.1:3000`; `/api/*` is rewritten to `http://api:8000` inside the compose network |
| `db` | `postgres:18`, named volume, no published port; the API applies migrations on start |

Neither application container mounts a host path or the Docker socket. The only writable places are
`/tmp` and, for `web`, `/app/.next/cache` — both tmpfs, both discarded on restart.

`deploy.sh` is what `ssh roomly-deploy@host 'deploy v2.2.0'` actually runs:

1. reject anything that is not `deploy v<semver>`;
2. `docker compose pull` — a missing tag fails here, before anything is restarted;
3. `docker compose up -d`, which recreates the containers whose image tag changed;
4. poll for 30s: `/health` must answer `"database":"postgres"`, `/sign-in` must return 200, and
   `/api/health` must answer through the frontend (this proves the rewrite, not just the API);
5. on failure, bring the previous tag back up and exit non-zero, so the workflow goes red;
6. on success, record the tag in `.current`.

Rolling back by hand is the same command with an older tag — the image is still in ghcr:

```sh
ssh roomly-deploy@<host> 'deploy v2.2.0'
```

Migrations are forward-only and run when the API starts, so an incompatible schema shows up as a
failed health check and an automatic rollback. Keep schema changes compatible with the release
before them (add and backfill first, drop in a later release), or the rollback restores code the
schema no longer fits.

## One-time: the host

Docker is already on the machine; the compose v2 plugin is not (`apt install docker-compose-v2`; the
Ubuntu `docker-compose` 1.x package does not understand this file). Everything below is done once,
as root.

```sh
adduser --disabled-password --gecos "" roomly-deploy
usermod -aG docker roomly-deploy

install -d -o root -g roomly-deploy -m 750 /srv/roomly
install -m 644 deploy/docker-compose.yml /srv/roomly/docker-compose.yml
install -m 755 deploy/deploy.sh /srv/roomly/deploy.sh
install -m 640 -o root -g roomly-deploy deploy/.env.example /srv/roomly/.env
$EDITOR /srv/roomly/.env                     # POSTGRES_PASSWORD, ROOMLY_MAIL_SECRET
install -o roomly-deploy -g roomly-deploy -m 644 /dev/null /srv/roomly/.current
```

`roomly-deploy` needs to read `.env` and write `.current`, and to talk to Docker. It has no shell of
its own in practice — the deploy key is forced to `deploy.sh`:

```sh
install -d -m 700 -o roomly-deploy -g roomly-deploy /home/roomly-deploy/.ssh
cat >>/home/roomly-deploy/.ssh/authorized_keys <<'EOF'
restrict,command="/srv/roomly/deploy.sh" ssh-ed25519 AAAA... roomly-deploy-ci
EOF
chown roomly-deploy:roomly-deploy /home/roomly-deploy/.ssh/authorized_keys
chmod 600 /home/roomly-deploy/.ssh/authorized_keys
```

GitHub's runners cannot reach a tailnet address, so sshd needs a listener on the public address.
Keep it narrow: a separate port, usable by the deploy account only, public keys only.

```sh
cat >>/etc/ssh/sshd_config <<'EOF'
ListenAddress <public-ip>:2222
Match LocalPort 2222
    AllowUsers roomly-deploy
    PermitRootLogin no
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    AuthenticationMethods publickey
    AllowTcpForwarding no
    X11Forwarding no
EOF
sshd -t && systemctl reload ssh
```

`restrict` disables pty, forwarding and agent use; the command string only reaches
`$SSH_ORIGINAL_COMMAND`. A leaked key can deploy a tag and nothing else — it cannot read `.env`, get
a shell, or run `docker` directly.

nginx and the origin certificate:

```sh
install -m 644 deploy/nginx-roomly.conf /etc/nginx/sites-available/roomly
ln -sf /etc/nginx/sites-available/roomly /etc/nginx/sites-enabled/roomly
rm -f /etc/nginx/sites-enabled/default

install -d -m 755 /etc/ssl/cloudflare
install -m 644 roomly.bid.pem /etc/ssl/cloudflare/roomly.bid.pem   # Cloudflare Origin Certificate
install -m 600 roomly.bid.key /etc/ssl/cloudflare/roomly.bid.key

nginx -t && systemctl enable --now nginx && systemctl reload nginx
```

The firewall only needs 22, 80 and 443. Restricting 443 to the [Cloudflare ranges](https://www.cloudflare.com/ips/)
keeps the origin from being reached directly.

## One-time: Cloudflare

1. `roomly.bid` on Cloudflare nameservers; `A roomly.bid` and `A www` → the VPS, proxied.
   `mail.roomly.bid` gets no record: the Worker route creates it.
2. SSL/TLS: **Full (strict)**, Always Use HTTPS, minimum TLS 1.2.
3. Workers **Paid** plan — outbound mail is only available there, 3,000 messages a month included.
4. Email Service → onboard `roomly.bid` as a sending domain; SPF and DKIM are published for you.
   Wait until the domain reports ready.
5. DMARC, permissive first. Enabling Email Sending creates `_dmarc` as `p=reject`; change it:

   ```
   _dmarc.roomly.bid  TXT  "v=DMARC1; p=none; rua=mailto:dmarc@roomly.bid; adkim=r; aspf=r"
   ```

6. Email Routing: enable it, then route `support@roomly.bid` and `dmarc@roomly.bid` to the
   **roomly-mail** Worker. No catch-all: the CLI can only forward or drop there, and other
   addresses should not be accepted. Deploy the Worker first; there is nothing to route to until it
   exists:

   ```sh
   wrangler email routing enable roomly.bid
   for a in support dmarc; do
     wrangler email routing rules create roomly.bid --name "$a to roomly-mail Worker" \
       --match-type literal --match-field to --match-value "$a@roomly.bid" \
       --action-type worker --action-value roomly-mail
   done
   ```
 The Worker forwards support mail to `SUPPORT_INBOX`: a real mailbox outside the
   domain, added under Email Routing → Destination addresses and verified. It is a Worker secret
   because this repository is public, and it must not be `support@roomly.bid` (that would forward
   to itself):

   ```sh
   pnpm exec wrangler secret put SUPPORT_INBOX --env production   # in mail/
   ```

   `SUPPORT_ADDRESS` (the public `support@roomly.bid`) is a plain var; it is the Reply-To of
   outbound mail. With `SUPPORT_INBOX` unset, inbound mail is logged and dropped.
7. ghcr: both packages (`roomly-api`, `roomly-web`) must be **public**, otherwise the host needs a
   registry credential. A package exists only after its first push, so the first tag's deploy step
   fails on `pull`; then make both public (Packages → the package → Package settings → Change
   visibility) and re-run the failed job (`gh run rerun <id> --failed`).

## GitHub configuration

Repository secrets:

| Secret | Value |
| --- | --- |
| `DEPLOY_HOST` | VPS address |
| `DEPLOY_PORT` | `2222`, the public sshd listener below (defaults to 22 when unset) |
| `DEPLOY_USER` | `roomly-deploy` |
| `DEPLOY_SSH_KEY` | private key, full contents |
| `DEPLOY_KNOWN_HOSTS` | `[<host>]:2222 <contents of /etc/ssh/ssh_host_ed25519_key.pub>`, taken from the host itself rather than scanned over the network |
| `CLOUDFLARE_API_TOKEN` | Account → Workers Scripts: Edit; Zone (`roomly.bid`) → Workers Routes: Edit, DNS: Edit |
| `CLOUDFLARE_ACCOUNT_ID` | Workers overview in the dashboard |
| `MAIL_SECRET` | `openssl rand -hex 32`; the same value as `ROOMLY_MAIL_SECRET` in `/srv/roomly/.env` |

`GITHUB_TOKEN` pushes the images, so there is no registry secret at all.

## What a compromised container can reach

| Can | Cannot |
| --- | --- |
| read its own environment: DB password for this one database, `ROOMLY_MAIL_SECRET` | reach the host filesystem: nothing is mounted |
| query that database, answer HTTP as the app | restart itself, change its image, or run `docker` |
| make outbound connections | read `.env` from the host, the deploy key, or the Cloudflare token |
| fill its own tmpfs and memory (capped at 512 MB, 256 pids) | escalate: non-root user, `cap_drop: ALL`, `no-new-privileges` |

Rotating: `POSTGRES_PASSWORD` (edit `.env`, `docker compose up -d`), `MAIL_SECRET` (edit `.env`, the
GitHub secret, and `wrangler secret put MAIL_SECRET --env production`, then redeploy), deploy key
(regenerate, replace the `authorized_keys` line).

## Day to day

```sh
cd /srv/roomly
docker compose ps
docker compose logs -f api
curl -fsS http://127.0.0.1:8000/health   # {"status":"ok","database":"postgres"}
```

`"database"` must be `postgres`; `sqlite` or null means the API fell back or never opened the
primary, and `deploy.sh` treats it as a failed deploy.

Mail problems are usually configuration, not code:

| Symptom | Cause |
| --- | --- |
| `E_SENDER_DOMAIN_NOT_AVAILABLE` | sending domain not onboarded, or onboarding unfinished |
| `E_RECIPIENT_PLAN_RESTRICTED` | Workers Free, or a recipient that is not a verified destination |
| `E_ACCOUNT_SUSPENDED` | sending reputation; Cloudflare paused the account |
| `/v1/send` answers `not_configured` | `MAIL_SECRET` missing on that Worker environment |
| `stale_timestamp` | host and Cloudflare clocks differ by more than five minutes |

A new `.bid` domain lands in spam far more often than a `.com`. Keep DMARC at `p=none` until the
reports look clean, and verify a real Gmail and Outlook address before the first release that
depends on verification mail.
