#!/usr/bin/env bash
set -euo pipefail
umask 077
: "${PGHOST:?Set PGHOST}" "${PGUSER:?Set PGUSER}" "${PGDATABASE:?Set PGDATABASE}"
# Password belongs in PGPASSFILE, never a command-line URL.
: "${PGPASSFILE:?Set a mode-0600 PGPASSFILE}"
output=${1:?Usage: production-backup.sh NEW_OUTPUT.dump}
[[ ! -e "$output" && ! -e "$output.partial" ]] || { printf '%s\n' 'Refusing to overwrite existing backup' >&2; exit 1; }
trap 'rm -f -- "$output.partial"' EXIT
pg_dump --format=custom --no-owner --no-acl --file="$output.partial"
pg_restore --list "$output.partial" >/dev/null
mv -- "$output.partial" "$output"
(cd -- "$(dirname -- "$output")" && sha256sum "$(basename -- "$output")") > "$output.sha256"
printf 'Verified archive structure: %s\n' "$output"
