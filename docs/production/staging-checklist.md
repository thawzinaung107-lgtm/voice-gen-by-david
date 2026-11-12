# Staging environment checklist — Voice Gen By David V2

Before production deployment, the following external resources must be configured and verified. Each item lists what is needed, where it goes, and how to verify.

## 1. Supabase project

Create a Supabase project (free tier or paid). Collect:

| Value | Where it goes | Notes |
|-------|---------------|-------|
| `SUPABASE_URL` | backend env + `/health` public config | `https://<ref>.supabase.co` |
| `SUPABASE_ANON_KEY` | backend env → `/health` public config | publishable/anon key only — never service_role |
| `SUPABASE_ISSUER` | backend env | `https://<ref>.supabase.co/auth/v1` |
| `SUPABASE_JWKS_URL` | backend env | `https://<ref>.supabase.co/auth/v1/.well-known/jwks.json` |
| `DATABASE_URL` | backend env (runtime role) | `postgresql+psycopg://voicegen_api:<pw>@db.<ref>.supabase.co:5432/postgres` |
| `WORKER_DATABASE_URL` | worker env | same but `voicegen_worker` role |

**Verify:**
- `alembic upgrade head` against the Supabase DATABASE_URL as the migration owner.
- Create a test user via Supabase Auth → get a JWT → `POST /api/session` → `GET /api/me` returns user + wallet.
- Cross-user access: user A's generations/audio/topups invisible to user B.
- RLS: runtime role cannot see other users' rows when `app.user_id` is unset.

## 2. Cloudflare R2 bucket

Create a private R2 bucket (no public access). Collect:

| Value | Where it goes | Notes |
|-------|---------------|-------|
| `S3_ENDPOINT_URL` | backend env | `https://<account_id>.r2.cloudflarestorage.com` |
| `S3_BUCKET` | backend env | bucket name |
| `S3_ACCESS_KEY_ID` | backend env | R2 API token with read/write |
| `S3_SECRET_ACCESS_KEY` | backend env | paired secret |

**Verify:**
- Upload evidence → check object exists in bucket, not publicly accessible.
- Admin evidence endpoint streams correctly with Content-Disposition attachment.
- Audio streaming works with byte ranges after generation.
- Lifecycle policy: set bucket rule to delete objects older than 30 days (eventual cleanup; app enforces 24h access separately).

## 3. Vibi supplier

Rotate the staging API key. Collect:

| Value | Where it goes | Notes |
|-------|---------------|-------|
| `VIBI_API_KEY` | backend env (worker + app) | new key, never reuse staging |
| `VIBI_BASE_URL` | backend env | `https://api.vibi.pro` |
| `CREDIT_PER_CHARACTER` | backend env | integer credits per character — needs real pricing decision |
| `SUPPLIER_ENABLED` | backend env | `true` only after supplier contract verified |

**Verify:**
- GET `/voices` returns real Vibi catalog.
- `POST /generate` creates task → worker polls → completed → audio downloadable.
- Concurrent duplicate `request_id` → same task, no double-debit.
- Crash between submission and response → outbox retains uncertain state → reconciliation works.

## 4. GenMax fallback (optional, deferred)

Keep `GENMAX_ENABLED` absent/false until Vibi is live and GenMax API contract is independently verified.

## 5. Domain + TLS

- `voicegen.atbd.space` — confirm ownership and DNS write access.
- Caddy config: `deploy/Caddyfile.template` — replace `VOICEGEN_DOMAIN` placeholder.
- APP_ORIGIN: `https://voicegen.atbd.space`.

## 6. Monitoring

| Value | Where it goes | Notes |
|-------|---------------|-------|
| `SENTRY_DSN` | backend env | optional — if set, sentry_sdk initializes |
| Log shipping | `journalctl -u voicegen` or Docker logs | JSON structured logs already emitted |

## Required env summary

```
APP_ORIGIN=https://voicegen.atbd.space
DATABASE_URL=postgresql+psycopg://voicegen_api:<pw>@db.<ref>.supabase.co:5432/postgres
WORKER_DATABASE_URL=postgresql+psycopg://voicegen_worker:<pw>@db.<ref>.supabase.co:5432/postgres
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_ANON_KEY=<anon-key>
SUPABASE_ISSUER=https://<ref>.supabase.co/auth/v1
SUPABASE_AUDIENCE=authenticated
SUPABASE_JWKS_URL=https://<ref>.supabase.co/auth/v1/.well-known/jwks.json
S3_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
S3_BUCKET=<bucket-name>
S3_ACCESS_KEY_ID=<r2-key>
S3_SECRET_ACCESS_KEY=<r2-secret>
VIBI_API_KEY=<rotated-key>
VIBI_BASE_URL=https://api.vibi.pro
CREDIT_PER_CHARACTER=<pricing-integer>
SUPPLIER_ENABLED=true
SENTRY_DSN=<optional>
```
