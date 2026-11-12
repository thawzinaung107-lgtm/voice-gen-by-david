# Local verification evidence

Verified 2026-11-10 against the shared checkout as files were completed. No public deployment or DNS write was performed.

| Check | Actual result |
|---|---|
| `npm run typecheck` | Passed |
| `npm run build` | Passed, Vite production assets emitted |
| stdlib staging backend unittest discovery | 9 tests passed |
| `node tests/phase2-ui.cjs` | Mock-only E2E passed |
| PostgreSQL backup/restore drill | Passed archive listing, SHA-256, restored 2 rows/net 220, rejected nonempty target |
| test and production `docker compose ... config --quiet` | Passed; production validation used `/dev/null` env and a local placeholder image |
| Caddy template validation | Valid configuration; template formatted afterward |
| Docker backend image build | Built successfully as `voicegen-ops-verification:local` |
| `production-verify-image.sh` | Alembic forward migration + 20 production tests passed in fresh tmpfs PostgreSQL |
| API process smoke | UID 10001, read-only filesystem, health 200, anonymous `/api/me` 401 |
| DNS | Spaceship NS; proposed hostname A/AAAA/TXT NXDOMAIN; ownership unknown |

An earlier snapshot produced one reconciliation test failure (expired pending job returned 409). A subsequent core fix and image rebuild passed all 20 tests. One upstream Starlette/AnyIO deprecation warning remains. Docker's installed legacy builder warns that BuildKit/buildx is absent; it ignores Dockerfile-specific context filtering and transferred approximately 330 MB of repository context locally. The image copies only requirements, production, Alembic and reviewed logging files; use BuildKit in release CI to honor `deploy/Dockerfile.dockerignore`. Never include private env files anywhere inside the build context.

Hosted GitHub Actions has not run here. Supabase account configuration, remote R2 permissions, real payment settlement verification, provider integration, TLS issuance, Sentry delivery, alert delivery, real-data restore, migration rollback rehearsal and public cutover remain staging/release gates. Current supplier and optional GenMax adapters remain disabled pending upstream contract verification. See runbooks for required evidence; passing local synthetic tests does not satisfy those external gates.
