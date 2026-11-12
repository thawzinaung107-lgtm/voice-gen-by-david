# Security and financial operations

## Supabase/Postgres roles

Use the owner only for migrations. API/worker login roles must be NOINHERIT, NOSUPERUSER and NOBYPASSRLS, and may assume only the expected runtime role. Inspect both the login and effective role because `SET LOCAL ROLE` changes privileges. A connection that silently remains owner can invalidate every tenant-isolation result.

Run read-only catalog checks with the exact runtime login and inside the same transaction/role context used by the app:

```sql
SELECT session_user, current_user;
SELECT rolname, rolsuper, rolbypassrls, rolinherit FROM pg_roles
 WHERE rolname IN (session_user, current_user, 'voicegen_api', 'voicegen_worker');
SELECT n.nspname, c.relname, pg_get_userbyid(c.relowner) AS owner,
 c.relrowsecurity, c.relforcerowsecurity
 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relkind IN ('r','p');
SELECT schemaname, tablename, policyname, roles, cmd, qual, with_check
 FROM pg_policies WHERE schemaname='public';
```

Reject runtime ownership, superuser, BYPASSRLS or membership in owner/service roles. Require RLS (and FORCE where appropriate) on tenant tables. Check table grants as well as policies; broad `PUBLIC`, `anon` or `authenticated` grants can expose tables through Supabase REST even when FastAPI checks are correct. Exercise two independent identities, forged/expired/wrong-audience JWTs and missing tenant claims. Test via actual runtime credentials, not solely owner connections with request headers. Production tests must also prove tenant A cannot read tenant B history, audio or payment evidence. Auth state and admin authority come from verified identity/database state, never client role fields.

## Manual payments

A reviewer independently checks bank/settlement account records: received amount, currency, destination, timestamp, unique external reference and purchaser. Screenshot evidence is private and untrusted. Reviewers cannot approve their own topups. Approval must be idempotent and transactional: unique verified reference + approved state + one ledger credit + immutable audit. A repeated approval or concurrent second admin must never add credits twice. Keep the reference separate from the user's claimed reference. Record reviewer identity, reason and independent verification evidence; never log bank secrets or upload URLs. Reversals use compensating immutable ledger/audit events, never UPDATE/DELETE of financial history. Pending payments never increase spendable credit. Verify conversion policy before enabling sales; no payment provider is integrated.

## Private audio and evidence

R2 bucket remains private: disable public `r2.dev`, public bucket domains and wildcard public ACLs. Only scoped server credentials may read/write objects. User receives authenticated `/api/audio/{id}` streaming after ownership and expiry checks, never a raw supplier URL/public R2 URL or a long-lived presigned URL. Verify GET, HEAD and Range return denial for foreign users, logged-out users and requests at/after the 24-hour cutoff. Access expiry is enforced by the app even if an object still exists. Lifecycle cleanup is a separate scheduled operation with metrics and dry-run review; it must not determine access policy. Keep financial/audit records beyond audio cleanup under the approved retention policy. Topup evidence follows its own restricted retention policy.
