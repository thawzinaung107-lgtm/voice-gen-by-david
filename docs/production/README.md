# Production operations and release gates

The existing `node server.mjs` entrypoint delegates to `server/backend.py`, a Python stdlib HTTP service using private SQLite/audio storage and single-owner authentication. Its tests and phase2 UI fixtures remain staging regression coverage. The production target is React/Vite + FastAPI + Supabase Postgres/Auth + private Cloudflare R2. These deployment files are release candidates; a passing syntax check does not establish production readiness. No cloud account, public listener, DNS change, live payment, or supplier generation is authorized by these files.

## Local verification

VPS without Supabase or R2: `deploy/compose.vps.yml` starts Postgres 16 and MinIO on loopback only. Copy `deploy/vps.env.example` outside the checkout, create the NOINHERIT runtime roles after `alembic upgrade head`, and set `AUTH_MODE=local`. Do not publish 5432 or 9000. Do not install the Caddyfile until the domain owner approves DNS.


From repository root:

```sh
npm ci
npm run typecheck
npm run build
python3 -m unittest discover -s server -p 'test_*.py' -v
npx playwright install chromium
node tests/phase2-ui.cjs
docker compose -f deploy/compose.test.yml config --quiet
docker compose -f deploy/compose.test.yml up -d --wait
# ONLY this test PostgreSQL; never point tests at a shared database.
export TEST_DATABASE_URL='postgresql+psycopg://voicegen_test:voicegen_test@127.0.0.1:55432/voicegen_test'
export DATABASE_URL="$TEST_DATABASE_URL"
python3 -m pip install -r requirements-dev.txt
alembic upgrade head
python3 -m pytest tests/production -q
bash scripts/production-restore-drill.sh
caddy validate --config deploy/Caddyfile.template --adapter caddyfile
python3 scripts/production-dns-preflight.py
```

The test Compose project is `voicegen-production-test`; its database publishes only `127.0.0.1:55432` and persists in its own project-scoped volume. Stop with `docker compose -f deploy/compose.test.yml down` (without `-v`). Never run global Docker prune or delete existing volumes. The restore drill uses a unique temporary container with tmpfs, no published ports, and removes only that container on exit.

CI executes typecheck/build, all stdlib backend tests, mock-only phase2 UI, production PostgreSQL migrations/tests, backend image build, and the restore drill. No cloud credentials are supplied. Do not add live supplier or payment calls to CI. CI runs from GitHub after the parent owner publishes the repository; local files alone are not evidence that hosted CI ran.

## Release gates, in order

1. Record commit and immutable image digest. Build `docker build -f deploy/Dockerfile -t voicegen:<commit> .`; archive the matching Vite `dist` separately. Confirm production app entrypoint and runtime environment against `production/README.md`. No production traffic until all production tests execute (no silent PostgreSQL skips).
2. Obtain independent domain-owner evidence and explicit approval for DNS/TLS/public cutover. `voicegen.atbd.space` is proposed only. Public DNS answers do not prove account ownership. See `dns-preflight.md`.
3. Create isolated staging resources with separate credentials. Rotate any previously shared staging supplier tokens and owner tokens before production; production never reuses staging credentials. Configure asymmetric Supabase JWT issuer/audience/JWKS, HTTPS origin, private R2 credentials and verified integer pricing. No secrets belong in Vite `VITE_*` variables, images, logs or git.
4. Use separate migration owner, API and worker logins. Audit RLS and owner-bypass checks in `security-and-payments.md`; verify cross-user API/object denial, expired audio/HEAD/range denial and immutable ledger/audit writes. Supabase service-role credentials must never reach the browser.
5. Migrate a restored staging database first. Verify current revision, forward migration, old/new code compatibility and immutable accounting balances. Take and restore-test an encrypted backup before production migration. Never improvise destructive downgrade.
6. Test restart/outbox recovery without live suppliers: concurrent reserve/debit, idempotency, insufficient funds, worker crash before/after submission and uncertain state. Unknown submission must retain the reservation and require reconciliation, never automatic redispatch. Vibi is primary; GenMax stays disabled until compatible semantics are independently confirmed.
7. Verify manual topup against an independent settlement record, admin separation, duplicate settlement reference rejection and concurrent approval. Screenshots alone must never credit wallets. There are no live payment integrations.
8. Review backup retention/restore evidence, alert delivery, worker supervision and structured log redaction. Sentry names in env example are templates, not proof instrumentation exists. See `monitoring.md`.
9. Only after explicit deployment authorization: place private env outside checkout, set `VOICEGEN_ENV_FILE` absolute path and `VOICEGEN_IMAGE` digest, validate `docker compose -f deploy/compose.production.yml config --quiet`, run migrations as owner once, start API and separately reviewed worker, then validate loopback health/auth before activating host Caddy. Production Compose intentionally has no database and no public API bind. The optional `--profile worker` starts `python -m production.worker`; leave it off until the supplier adapter, storage wiring and worker heartbeat are reviewed. Current default worker supplier is disabled and cannot dispatch live jobs. Its API HTTP healthcheck is disabled because a worker has no HTTP listener.

The API container listens on 8000 internally and is published only on host loopback 18787. Host Caddy serves an immutable frontend release via `/srv/voicegen/current/dist`; `/api` proxies to that loopback port preserving Host. Uvicorn trusts forwarded headers only from loopback; a bridge-network Caddy is not part of this template. Do not broaden trust to `*`. Secure cookies derive from configured HTTPS origin. Validate origin and scheme in staging before release.

## Rollback

Stop or pause workers/dispatch first; preserve database/outbox evidence and reservations. Repoint the frontend release symlink and pin the previous API digest only when schema is backward-compatible. Verify health, login, tenant isolation and accounting before reopening writes. If a migration is incompatible, keep maintenance mode and restore to a new isolated database, reconcile all post-backup payments, ledger events and supplier submissions, then seek an explicit cutover decision. A blind `alembic downgrade` can destroy financial/audit records and is prohibited. Do not delete or mutate old ledger/audit rows to force reconciliation; append authorized compensating entries with reason and independent references.
