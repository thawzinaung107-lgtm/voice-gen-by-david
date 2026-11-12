#!/usr/bin/env bash
set -euo pipefail
umask 077
: "${PGHOST:?Set PGHOST}" "${PGUSER:?Set PGUSER}" "${PGDATABASE:?Set PGDATABASE}"
: "${PGPASSFILE:?Set a mode-0600 PGPASSFILE}"
archive=${1:?Usage: production-restore.sh BACKUP.dump}
# Only restore to a fresh recovery database. Never clean, drop or overwrite.
[[ "${VOICEGEN_RESTORE_TARGET:-}" == "$PGDATABASE" && "$PGDATABASE" == voicegen_restore_* ]] || { printf '%s\n' 'Target must be a fresh voicegen_restore_* database; set VOICEGEN_RESTORE_TARGET to its exact name' >&2; exit 1; }
(cd -- "$(dirname -- "$archive")" && sha256sum -c "$(basename -- "$archive").sha256")
count=$(psql -X -A -t -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%' AND c.relkind IN ('r','p','v','m','S','f');")
[[ "$count" == 0 ]] || { printf '%s\n' 'Refusing restore into nonempty database' >&2; exit 1; }
pg_restore --exit-on-error --single-transaction --no-owner --no-acl --dbname="$PGDATABASE" "$archive"
printf 'Restored into isolated target: %s; perform application and ledger checks before cutover.\n' "$PGDATABASE"
