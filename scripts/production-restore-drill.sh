#!/usr/bin/env bash
set -euo pipefail
# Ephemeral database only: no ports and no existing volumes are touched.
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
name="voicegen-restore-drill-$(date +%s)-$$"
cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT
image=${POSTGRES_TEST_IMAGE:-postgres:16-alpine}
docker run --detach --name "$name" --tmpfs /var/lib/postgresql/data --tmpfs /drill --env POSTGRES_PASSWORD=local-drill-password --mount "type=bind,src=$repo/scripts,dst=/ops,readonly" "$image" >/dev/null
ready=0
for attempt in {1..60}; do
  if docker exec "$name" pg_isready -U postgres >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
[[ "$ready" == 1 ]] || { docker logs "$name"; exit 1; }
docker exec "$name" bash -c 'umask 077; printf "%s\n" "127.0.0.1:5432:*:postgres:local-drill-password" > /drill/pgpass'
docker exec "$name" createdb -U postgres voicegen_source
docker exec "$name" createdb -U postgres voicegen_restore_drill
docker exec "$name" psql -U postgres -d voicegen_source -v ON_ERROR_STOP=1 -c "CREATE TABLE drill_ledger(id bigint PRIMARY KEY, credits bigint NOT NULL); INSERT INTO drill_ledger VALUES (1,250),(2,-30);"
docker exec --env PGHOST=127.0.0.1 --env PGUSER=postgres --env PGDATABASE=voicegen_source --env PGPASSFILE=/drill/pgpass "$name" bash /ops/production-backup.sh /drill/backup.dump
docker exec --env PGHOST=127.0.0.1 --env PGUSER=postgres --env PGDATABASE=voicegen_restore_drill --env VOICEGEN_RESTORE_TARGET=voicegen_restore_drill --env PGPASSFILE=/drill/pgpass "$name" bash /ops/production-restore.sh /drill/backup.dump
actual=$(docker exec "$name" psql -U postgres -d voicegen_restore_drill -X -A -t -c 'SELECT count(*)::text || chr(58) || sum(credits)::text FROM drill_ledger;')
[[ "$actual" == '2:220' ]] || { printf 'Restore data mismatch: %s\n' "$actual" >&2; exit 1; }
if docker exec --env PGHOST=127.0.0.1 --env PGUSER=postgres --env PGDATABASE=voicegen_restore_drill --env VOICEGEN_RESTORE_TARGET=voicegen_restore_drill --env PGPASSFILE=/drill/pgpass "$name" bash /ops/production-restore.sh /drill/backup.dump; then
  printf '%s\n' 'ERROR: nonempty restore target accepted' >&2; exit 1
fi
printf '%s\n' 'PASS: actual backup and isolated restore preserved 2 ledger rows / net 220; nonempty target rejected.'
