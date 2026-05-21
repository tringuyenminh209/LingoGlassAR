# EC2 deploy scripts

These scripts bootstrap and redeploy the S1 backend on a single Ubuntu 22.04 ARM EC2 instance in AWS Osaka. `bootstrap.sh` provisions Docker, firewall rules, the `deploy` user, and the checkout directory; `deploy.sh` updates `/home/deploy/lingoglass` from `main` and runs the backend Docker Compose stack.

## First time

Follow `docs/runbook/aws-osaka-deploy.md` for the EC2 launch, Elastic IP, Cloudflare DNS, first clone, and `.env` creation. Run `bootstrap.sh` only after the runbook tells you to copy it to the instance.

## Redeploy

```bash
bash infra/ec2/deploy.sh
```

## Troubleshooting

- SSH timeout or Cloudflare `522`: check firewall and security group rules with `sudo ufw status verbose`.
- Missing backend secrets: verify the file exists with `ls -l /home/deploy/lingoglass/backend/.env`.
- API container not running: inspect Compose state with `cd /home/deploy/lingoglass/backend && docker compose ps`.
- Redis unhealthy or `/healthz` returns `redis: "down"`: inspect Redis logs with `cd /home/deploy/lingoglass/backend && docker compose logs redis --tail 30`.
- Cloudflare `526`: confirm SSL/TLS mode is `Full`, not `Full (strict)`, in the Cloudflare dashboard.
