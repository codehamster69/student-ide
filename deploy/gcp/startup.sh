#!/bin/bash
# Student IDE VM: on every boot, fetch the latest release + .env from the deploy bucket and (re)start the stack.
set -euxo pipefail
B=gs://studentide-iiits-1026-deploy
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
  apt-get install -y unattended-upgrades
fi
mkdir -p /opt/studentide && cd /opt/studentide
gcloud storage cp $B/studentide.tar.gz $B/deploy.env /tmp/
rm -rf src.new && mkdir src.new && tar -xzf /tmp/studentide.tar.gz -C src.new
rm -rf src && mv src.new src
install -m 600 /tmp/deploy.env src/deploy/.env
cd src/deploy && docker compose up -d --build --remove-orphans
docker compose ps
echo "STUDENTIDE DEPLOY DONE"
# smoke test, visible on the serial console
sleep 20
# A hard reset during certificate issuance leaves a truncated file in Caddy's store; drop it so Caddy re-issues.
caddy_logs=$(docker compose logs caddy 2>&1 || true)
if [[ $caddy_logs == *"decoding certificate metadata"* ]]; then
  docker compose rm -sf caddy && docker volume rm studentide_caddy_data && docker compose up -d caddy
fi
sleep 40
echo "SMOKE caddy: $(docker compose logs caddy --tail 12 2>&1 | grep -iE 'certificate|error|obtain' | cut -c1-300 | tr '\n' ' ')"
echo "SMOKE local: $(curl -sS -m 10 --resolve studentide.hokora.xyz:443:127.0.0.1 https://studentide.hokora.xyz/api/auth/config 2>&1)"
echo "SMOKE public: $(curl -sS -m 10 https://studentide.hokora.xyz/api/auth/config 2>&1)"
echo "SMOKE headers: $(curl -sSI -m 10 --resolve studentide.hokora.xyz:443:127.0.0.1 https://studentide.hokora.xyz/ 2>&1 | tr -d '\r' | grep -iE '^HTTP|strict-transport' | tr '\n' ' ')"
echo "SMOKE teach without sign-in: $(curl -s -m 10 -o /dev/null -w '%{http_code}' --resolve studentide.hokora.xyz:443:127.0.0.1 https://studentide.hokora.xyz/api/teach/labs)"
echo "SMOKE roll-number login: $(curl -s -m 10 -o /dev/null -w '%{http_code}' --resolve studentide.hokora.xyz:443:127.0.0.1 -H 'Content-Type: application/json' -d '{"student_id":"X1"}' https://studentide.hokora.xyz/api/login)"
echo "STUDENTIDE SMOKE DONE"
