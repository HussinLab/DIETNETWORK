#!/usr/bin/env bash
# Stand up the DIETNETWORK stack for a local test on a shared ICM server.
#
# This box already runs other projects' containers (see DX-Articles at
# /home/dx-llm/DX-Articles, whose own nginx owns host ports 80/443 and
# whose backend owns 127.0.0.1:8000), so this test deploy stays fully
# isolated: same production topology (Caddy/TLS in front of
# frontend+backend, Postgres/Redis internal-only) but remapped to
# 8080/8443, with MailHog standing in for real SMTP and CAPTCHA disabled.
# See docker-compose.local-test.yml for exactly what's overridden, and
# DEPLOYMENT.md for the non-test (Arbutus/Pulumi) deployment path.
#
# Usage: ./localDeployICM [down]
set -euo pipefail
cd "$(dirname "$0")"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.local-test.yml)

if [ "${1:-}" = "down" ]; then
  "${COMPOSE[@]}" down
  exit 0
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example — edit credentials/paths before running again."
  exit 1
fi

"${COMPOSE[@]}" config --quiet

"${COMPOSE[@]}" up --build -d

echo
echo "Deployed. Container status:"
"${COMPOSE[@]}" ps

cat <<'EOF'

--------------------------------------------------------------------
  App:        https://sgbmlesage01.icm.local:8443
              (Caddy-internal cert - browser will warn, expected)
  API direct: https://sgbmlesage01.icm.local:8443/api
  MailHog UI: http://sgbmlesage01.icm.local:8025 (view "sent" emails)
--------------------------------------------------------------------
Tail logs with:
  docker compose -f docker-compose.yml -f docker-compose.local-test.yml logs -f
Tear down with:
  ./localDeployICM down
EOF
