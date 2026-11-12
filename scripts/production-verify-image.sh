#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
image=${1:?Usage: production-verify-image.sh BUILT_IMAGE}
name="voicegen-image-test-$(date +%s)-$$"
api="$name-api"
cleanup() { docker rm -f "$api" "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT
# No published ports and no persistent volumes.
docker run -d --name "$name" --tmpfs /var/lib/postgresql/data -e POSTGRES_USER=voicegen_test -e POSTGRES_PASSWORD=voicegen_test -e POSTGRES_DB=voicegen_test postgres:16-alpine >/dev/null
ready=0
for attempt in {1..60}; do
  if docker exec "$name" pg_isready -U voicegen_test >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
[[ "$ready" == 1 ]]
url='postgresql+psycopg://voicegen_test:voicegen_test@127.0.0.1:5432/voicegen_test'
# Root is used solely to install pytest into this disposable test container.
# The actual API smoke container below retains Dockerfile's nonroot USER.
docker run --rm --user 0 --network "container:$name" -e DATABASE_URL="$url" -e TEST_DATABASE_URL="$url" -e PYTHONPATH=/app -v "$repo/tests/production:/suite:ro" "$image" sh -c 'pip install --no-cache-dir pytest==9.0.2 >/dev/null && alembic upgrade head && python -m pytest /suite -q -p no:cacheprovider'
docker run -d --name "$api" --network "container:$name" --read-only --tmpfs /tmp:rw,size=64m --cap-drop ALL --security-opt no-new-privileges -e DATABASE_URL="$url" -e APP_ORIGIN=https://voicegen.invalid -e SUPABASE_ISSUER=https://identity.invalid/auth/v1 -e SUPABASE_JWKS_URL=https://identity.invalid/jwks "$image" >/dev/null
ready=0
for attempt in {1..30}; do
  if docker exec "$api" python -c "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8000/api/health').status == 200" >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
[[ "$ready" == 1 ]] || { docker logs "$api"; exit 1; }
docker logs "$api" 2>&1 | python -c 'import json,sys; rows=[json.loads(line) for line in sys.stdin if line.strip()]; assert rows; assert any(row.get("event")=="http_access" and row.get("status")==200 for row in rows); assert all("unused" not in json.dumps(row) and "identity.invalid" not in json.dumps(row) for row in rows); print("PASS: server logs are parseable JSON without fixture credentials/URLs")'
docker exec "$api" python -c "import os,urllib.request,urllib.error; assert os.getuid()==10001; exec(\"try:\\n urllib.request.urlopen('http://127.0.0.1:8000/api/me')\\n raise AssertionError('Anonymous access accepted')\\nexcept urllib.error.HTTPError as error:\\n assert error.code==401\"); print('PASS: nonroot read-only API, health=200, anonymous me=401')"
