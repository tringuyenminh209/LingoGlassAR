# AWS Osaka EC2 + Cloudflare deploy runbook (S1 Day 4)

This is the manual steps the solo dev does in the AWS console + Cloudflare
dashboard. The matching automation lives in `infra/ec2/` (Codex S1 Day 4).
Total expected time: 60-90 min if no surprises.

Region: **ap-northeast-3 (Osaka)**. Domain: `lingoglass.online`
(Cloudflare-managed). Target hostname: `api.lingoglass.online`.

---

## 1. EC2 instance launch

1. AWS Console -> EC2 -> **Region selector top-right -> Asia Pacific (Osaka) ap-northeast-3**.
2. **Launch instances**.
3. **Name**: `lingoglass-prototype`.
4. **AMI**: Ubuntu Server 22.04 LTS (HVM), SSD Volume Type, **64-bit (Arm)**.
5. **Instance type**: `t4g.small` (2 vCPU Graviton2, 2 GB RAM). NOT `t3` or `t2` - those are x86. The Docker image must be multi-arch (it is — python:3.12-slim works on arm64).
6. **Key pair**: create new `lingoglass-osaka.pem`, download. Move to `~/.ssh/` locally, `chmod 600`.
7. **Network settings -> Edit**:
   - VPC: default OK
   - Subnet: any AZ in ap-northeast-3 (`apne3-az1`, `apne3-az2`, or `apne3-az3`)
   - Auto-assign public IP: Enable (we replace this with EIP later, but useful for first SSH)
   - **Firewall (security group)**: Create new, name `lingoglass-sg-prod`.
8. **Security group rules** (only these three, nothing else):
   - SSH (22/tcp), source: **My IP** (`x.x.x.x/32`). NOT 0.0.0.0/0.
   - HTTP (80/tcp), source: `0.0.0.0/0` and `::/0` (Cloudflare will be the only thing that hits this in practice; we keep it open at SG layer because Cloudflare IP ranges drift).
   - HTTPS (443/tcp), source: `0.0.0.0/0` and `::/0`.
9. **Storage**: 16 GB gp3 default is fine. Don't shrink — Docker images + Redis volume + logs add up.
10. **Advanced details -> User data**: leave empty. We bootstrap manually via SSH.
11. Click **Launch instance**.

## 2. Elastic IP allocation

1. EC2 -> Network & Security -> **Elastic IPs** -> **Allocate Elastic IP address**.
2. Network border group: `ap-northeast-3`. **Allocate**.
3. Select the new EIP -> Actions -> **Associate Elastic IP address**.
4. Resource type: Instance. Instance: `lingoglass-prototype`. **Associate**.
5. Copy the EIP — needed for Cloudflare DNS in step 5.

EIP cost: $0 while attached and instance is running; $3.6/mo if unassociated. Keep it attached.

## 3. First SSH + sanity check

```bash
ssh -i ~/.ssh/lingoglass-osaka.pem ubuntu@<EIP>
# Expected: Ubuntu 22.04.x LTS banner
sudo apt update
exit
```

If SSH times out: security group source IP wrong (your home IP changed). Edit `lingoglass-sg-prod` -> add current IP.

## 4. Bootstrap (run Codex's script)

After Codex's `infra/ec2/bootstrap.sh` is on `main`:

```bash
# Copy bootstrap script to the box (one-shot)
scp -i ~/.ssh/lingoglass-osaka.pem infra/ec2/bootstrap.sh ubuntu@<EIP>:/tmp/

# Run as root
ssh -i ~/.ssh/lingoglass-osaka.pem ubuntu@<EIP> "sudo bash /tmp/bootstrap.sh"
```

Expected output: docker version, compose plugin version, ufw active with 22/80/443, deploy user created. Re-running the script must exit 0 (idempotent).

After bootstrap:
- A user named `deploy` exists with docker group membership.
- The clone path `/home/deploy/lingoglass` exists.
- ufw is enabled and only 22/80/443 are open.

## 5. Cloudflare DNS

Prereq: domain `lingoglass.online` is already on Cloudflare (set up 2026-05-21).

1. Cloudflare dashboard -> `lingoglass.online` -> **DNS** -> **Records**.
2. **Add record**:
   - Type: `A`
   - Name: `api`
   - IPv4 address: `<EIP from step 2>`
   - Proxy status: **Proxied** (orange cloud)
   - TTL: Auto
   - Save.
3. **SSL/TLS** -> **Overview** -> set encryption mode to **Flexible**. This means: browser -> Cloudflare = HTTPS, Cloudflare -> origin = **HTTP port 80** (which is what our backend serves). Fine for prototype.

   IMPORTANT: do NOT pick "Full" or "Full (strict)" - those modes make Cloudflare connect to the origin on port 443 with TLS, but our origin has nothing on 443 and no certificate, so Cloudflare returns 521. Upgrade to "Full (strict)" in S2 by adding nginx or traefik in front of compose with a Let's Encrypt or Cloudflare Origin Certificate on port 443.
4. **SSL/TLS** -> **Edge Certificates** -> confirm "Always Use HTTPS" is **On**.
5. Wait 1-2 min for DNS to propagate.

## 6. First deploy (run Codex's script)

```bash
# As deploy user via sudo
ssh -i ~/.ssh/lingoglass-osaka.pem ubuntu@<EIP>
sudo -u deploy -i

# First-time clone
cd ~
git clone https://github.com/tringuyenminh209/LingoGlassAR.git lingoglass
cd lingoglass

# Create .env with real secrets (do NOT commit)
cd backend
cp .env.example .env
nano .env
# Set: OPENAI_API_KEY=sk-...
# Set: PUBLIC_BASE_URL=wss://api.lingoglass.online
# Set: CORS_ORIGINS=https://lingoglass.online,https://api.lingoglass.online
# Set: LOG_LEVEL=info
# Set: API_HOST_PORT=80   (production binding; required for Cloudflare Free plan)
# Leave REDIS_URL=redis://redis:6379/0

cd ..  # back to repo root
bash infra/ec2/deploy.sh
```

Expected: docker compose builds, brings up api + redis, healthcheck green within ~30 s.

## 7. Cloudflare smoke test (this is the Day 4 Go signal)

From your local machine:

```bash
curl -i https://api.lingoglass.online/healthz
# Expected:
#   HTTP/2 200
#   content-type: application/json
#   server: cloudflare
#   {"status":"ok","version":"0.1.0","redis":"up"}
```

If 200 with `redis: "up"` -> **Day 4 GO**.

Common failures:
- `522 Connection timed out` -> ufw blocked 80 (check `sudo ufw status`) or EIP wrong in Cloudflare DNS.
- `502 Bad gateway` -> docker compose not running on origin. SSH in, `cd ~/lingoglass/backend && docker compose ps`.
- `521 Web server is down` (origin direct curl works) -> Cloudflare SSL mode is "Full" or "Full (strict)" but origin only serves HTTP on port 80. Switch SSL mode to "Flexible".
- `526 Invalid SSL certificate` -> Cloudflare SSL mode set to "Full (strict)" but origin has no valid cert. Switch to "Flexible" for HTTP origin, or install a cert and stay on Full/Strict.
- `redis: "down"` in the body -> redis container not healthy. `docker compose logs redis --tail 30`.

## 8. Cost watch

- t4g.small: ~$0.022/hr in Osaka = **~$16/mo** if left running 24/7.
- EBS 16 GB gp3: **~$1.3/mo**.
- EIP attached: **$0** (only $3.6/mo if released-but-allocated).
- Outbound traffic: first 100 GB/mo free per account.

Expected baseline: **~$17/mo idle**. With OpenAI Realtime usage on top, watch
the Day 8 cost logger.

## 9. Tear-down (if rolling back)

```bash
# Stop only (preserves volume, EIP, instance)
ssh ubuntu@<EIP> "cd ~/lingoglass/backend && sudo -u deploy docker compose down"

# Hard tear-down (deletes the instance, releases EIP)
# AWS Console -> EC2 -> Instances -> Terminate.
# AWS Console -> EIPs -> Release.
```

## What to record after a successful Day 4

In the day's nippo:
- EIP (so it can be re-associated if instance is recreated).
- Cloudflare DNS record TTL.
- `docker compose ps` output and uptime.
- `curl -w "%{time_total}\n"` from local to confirm cold-start latency over Cloudflare.

Add `[[project-osaka-deploy]]` memory if any non-obvious decision was made
during the deploy (e.g. AZ choice, custom SG rule, EBS resize).
