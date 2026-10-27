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
cat > /tmp/langs.py <<'PY'
from studentide.runner import run_many
from studentide.providers import PROVIDERS
progs = {
    "python": "print(sum(map(int, input().split())))",
    "c": "#include <stdio.h>\nint main(){int a,b;scanf(\"%d %d\",&a,&b);printf(\"%d\\n\",a+b);}",
    "cpp": "#include <iostream>\nint main(){int a,b;std::cin>>a>>b;std::cout<<a+b<<std::endl;}",
    "java": "import java.util.*;\npublic class Main{public static void main(String[] x){Scanner s=new Scanner(System.in);System.out.println(s.nextInt()+s.nextInt());}}",
    "javascript": "const [a,b]=require('fs').readFileSync(0,'utf8').trim().split(' ').map(Number);console.log(a+b)",
}
for lang, code in progs.items():
    try:
        fail, res, _ = run_many(code, lang, ["1 2\n"])
        r = fail or res[0]
        print(f"{lang}={'ok' if r.stdout.strip() == '3' else 'FAIL ' + (r.error_type or '') + ' ' + r.stderr[:120].replace(chr(10), ' ')}", end=" ")
    except Exception as e:
        print(f"{lang}=FAIL {e!r}", end=" ")
print("| providers:", ",".join(sorted(PROVIDERS)))
PY
echo "SMOKE languages: $(docker compose exec -T app python - < /tmp/langs.py 2>&1 | tr '\n' ' ' | cut -c1-900)"
echo "STUDENTIDE SMOKE DONE"
