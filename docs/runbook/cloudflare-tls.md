# Cloudflare Full(Strict) origin TLS runbook (S2 Day 7-8)

Goal: move `api.lingoglass.online` from Cloudflare **Flexible** (edge HTTPS,
origin HTTP on :80) to **Full(Strict)** (edge HTTPS, origin HTTPS on :443 with
a valid certificate). This closes the last-mile gap where Cloudflare -> origin
traffic is currently unencrypted.

Region: ap-northeast-3 (Osaka). Origin: single t4g.small EC2 running the
backend Docker Compose stack behind Cloudflare (orange-cloud / proxied).

Prereq reading: `docs/runbook/aws-osaka-deploy.md` (S1 deploy, §5 explains why
Flexible was chosen and §7 lists the 521/526 failure modes this runbook fixes).

---

## 1. Cert path decision (locked)

**Chosen: Let's Encrypt issued via the DNS-01 challenge** (open question #3,
locked 2026-05-23). Rationale and the rejected alternatives:

| Option | TLS validity | Auto-renew | Works behind orange-cloud? | Verdict |
|---|---|---|---|---|
| **Let's Encrypt, DNS-01** | any client | yes (90 d, certbot.timer) | **yes** | **CHOSEN** |
| Let's Encrypt, HTTP-01 | any client | yes | **no** — see below | rejected |
| Cloudflare Origin Cert | only CF-fronted traffic | 15 yr, no renew | yes | rejected |

**Why not HTTP-01:** the `api` record is proxied (orange cloud). An HTTP-01
challenge is served on `http://api.lingoglass.online/.well-known/...`, which
resolves to Cloudflare's edge, not this origin — so certbot can never see its
own challenge token and issuance fails. Grey-clouding during issuance then
re-proxying works but is fragile and causes a brief direct-exposure window.

**Why not Cloudflare Origin Cert:** it is only trusted by Cloudflare, so a
direct `curl https://<EIP>` (bypassing CF for debugging) fails cert validation.
Keeping a publicly-trusted Let's Encrypt cert preserves the ability to debug
the origin directly — the deciding factor in open question #3.

**DNS-01 mechanics:** certbot proves zone control by creating a transient
`_acme-challenge` TXT record via the Cloudflare API, using the
`python3-certbot-dns-cloudflare` plugin and a scoped API token. No inbound
port needs to be reachable for issuance.

---

## 2. Prerequisites (operator, before running anything)

1. **Cloudflare API token** scoped as narrowly as possible:
   - Permissions: `Zone : DNS : Edit`
   - Zone Resources: `Include : Specific zone : lingoglass.online`
   - Create at Cloudflare dashboard -> My Profile -> API Tokens -> Create Token
     (use the "Edit zone DNS" template, then restrict the zone).
2. **Credentials file on the EC2** (never committed; mode 600):
   ```ini
   # /home/deploy/.secrets/cf-dns.ini
   dns_cloudflare_api_token = <the scoped token>
   ```
   ```bash
   sudo -u deploy install -d -m 700 /home/deploy/.secrets
   sudo -u deploy nano /home/deploy/.secrets/cf-dns.ini   # paste token line
   sudo chmod 600 /home/deploy/.secrets/cf-dns.ini
   ```
3. Confirm AWS security group + ufw already allow **443/tcp** (they do from S1
   — bootstrap opens 22/80/443). No SG change needed.

---

## 3. Run the TLS bootstrap extension

> The bootstrap functions `install_tls_proxy` / `issue_origin_cert` /
> `configure_nginx_reverse_proxy` are stubbed in `infra/ec2/bootstrap.sh`
> (Claude prep, S2 Day 7). **Codex fills the bodies + the exact commands in
> the placeholders below** (S2 Day 7 Codex row). Until then this section is a
> skeleton.

```bash
scp -i ~/.ssh/lingoglass-osaka.pem infra/ec2/bootstrap.sh ubuntu@<EIP>:/tmp/
ssh -i ~/.ssh/lingoglass-osaka.pem ubuntu@<EIP> \
  "sudo LINGOGLASS_TLS_PROXY=1 \
        ORIGIN_HOSTNAME=api.lingoglass.online \
        CF_DNS_CREDENTIALS_FILE=/home/deploy/.secrets/cf-dns.ini \
        bash /tmp/bootstrap.sh"
```

Expected (Codex to confirm exact output in the PR):
- `nginx -t` reports syntax OK and reload succeeds.
- `/etc/letsencrypt/live/api.lingoglass.online/fullchain.pem` exists.
- `systemctl is-enabled certbot.timer` -> `enabled` (auto-renew armed).
- Re-running the whole script is still idempotent and exits 0.

---

## 4. Point the backend at the proxy (compose/.env change)

Once nginx owns :443 (and :80), the backend container must stop binding the
public :80 and bind loopback instead, so only nginx is internet-facing.

- In `backend/.env` on the origin, change `API_HOST_PORT=80` so the published
  port maps to `127.0.0.1:8000` rather than `0.0.0.0:80`.
  > Codex: confirm whether this needs a compose edit (the current mapping is
  > `${API_HOST_PORT:-8000}:8000`, which binds all interfaces). If so, propose
  > the minimal `127.0.0.1:8000:8000` binding in the PR — do not change the
  > default behaviour for local dev.
- Redeploy: `bash infra/ec2/deploy.sh`.

---

## 5. Flip Cloudflare to Full(Strict)

1. Cloudflare dashboard -> `lingoglass.online` -> SSL/TLS -> Overview.
2. Set encryption mode **Full (strict)**.
3. Keep "Always Use HTTPS" On (Edge Certificates).

---

## 6. Smoke test (Day 8 GO signal)

```bash
# Through Cloudflare:
curl -i https://api.lingoglass.online/healthz
#   HTTP/2 200, server: cloudflare, {"status":"ok",...,"redis":"up"}

# Direct to origin, bypassing CF (proves the Let's Encrypt cert is valid to
# any client — the reason we did not use a Cloudflare Origin Cert):
curl -i --resolve api.lingoglass.online:443:<EIP> https://api.lingoglass.online/healthz
#   HTTP/2 200 with a valid (non-CF) certificate chain
```

GO when both return 200 and **no 521/526** appears in a **24 h** smoke window.

Failure modes (see also aws-osaka-deploy.md §7):
- `521 Web server is down` -> nginx not listening on 443, or backend upstream
  down. SSH in: `sudo nginx -t`, `sudo systemctl status nginx`,
  `cd ~/lingoglass/backend && docker compose ps`.
- `526 Invalid SSL certificate` -> origin cert missing/expired or SNI mismatch.
  Check `/etc/letsencrypt/live/.../fullchain.pem` and that `server_name`
  matches the proxied hostname.
- Issuance hangs -> wrong/over-scoped API token, or the credentials file is
  not mode 600.

---

## 7. Rollback

Flip Cloudflare SSL/TLS mode back to **Flexible**. The origin still answers
HTTP on the backend port, so traffic is restored immediately while the proxy
is debugged. (The nginx :443 listener can stay up; Flexible simply ignores it.)

---

## What to record after a successful Day 8

In the day's nippo and update `MEMORY.md` Cloudflare SSL memory
(Flexible -> Full(Strict)):
- Cert issuance timestamp + `certbot certificates` expiry date.
- `systemctl is-enabled certbot.timer` output.
- Both smoke `curl` results (through CF + direct-to-origin).
- Any SG/ufw or compose binding change that was actually needed.
