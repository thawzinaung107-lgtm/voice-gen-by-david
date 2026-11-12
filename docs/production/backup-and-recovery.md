# Backup and recovery

Use a dedicated encrypted backup destination outside the repository. Do not export secrets, Auth signing keys or R2 credentials into a database dump. Restrict access, encrypt at rest/in transit, keep checksum sidecar and record PostgreSQL version, commit, Alembic revision, UTC time, archive size and table/ledger totals. `pg_dump` is a transaction-consistent custom archive; use a compatible client version (PostgreSQL 16 for this test stack). Supabase platform Auth configuration and R2 objects require separate recovery plans: an application-schema dump alone is not a full platform backup.

`production-backup.sh` needs `PGHOST`, `PGPORT` if nondefault, `PGUSER`, `PGDATABASE`, `PGPASSFILE` (mode 0600), and normally `PGSSLMODE=verify-full` plus CA for a remote database. Use Supabase's supported direct/session connection for dumps rather than a transaction pooler. Credentials must never appear in command-line URLs. Script creates a private new archive, checks its archive listing and writes a portable SHA-256 sidecar. It refuses existing archive/partial paths and never prunes old backups. Copy archive and sidecar together to encrypted off-host storage and verify upload before considering the backup complete.

```sh
scripts/production-backup.sh /secure/backups/voicegen-RELEASE-UTC.dump
# Create a new recovery database manually under a dedicated recovery account.
export PGDATABASE=voicegen_restore_incident
export VOICEGEN_RESTORE_TARGET="$PGDATABASE"
scripts/production-restore.sh /secure/backups/voicegen-RELEASE-UTC.dump
```

Restore accepts only an explicitly confirmed `voicegen_restore_*` name and rejects databases containing user relations. It checks the sidecar, restores in one transaction with errors fatal, and never uses `--clean` or drops a database. Do not restore over production. Run a checksum test, schema revision comparison, row counts, immutable ledger sum/reservation reconciliation, foreign-key checks and two-user API isolation before any cutover. Restore does not preserve database owners/ACLs: reapply and verify reviewed runtime roles, grants, FORCE RLS and policies before connecting an API. Do not let a recovery owner become a runtime login.

`bash scripts/production-restore-drill.sh` runs the actual backup and restore scripts in an isolated PostgreSQL 16 container with tmpfs. It verifies two synthetic ledger rows and their net total survive, then proves a second restore into the nonempty target fails. This validates the mechanism; it does not substitute for restoring the real production schema and separately testing Supabase Auth/R2 recovery. No existing volumes or containers are deleted.

Proposed operating target pending owner acceptance: daily encrypted logical backup, at least 14 daily and 8 weekly copies, monthly full recovery drill, RPO <=24 hours and RTO <=4 hours. Measure actual restore time and alert on backup age >26 hours. Enable platform PITR separately if approved; logical backups alone cannot meet a lower RPO. Retention deletion requires an approved policy and a verified newer off-host copy; these scripts deliberately do not implement deletion.
