# Phase 2 single-owner staging backend

Run from the repository: `node server.mjs` (requires Python 3 and Node; no extra Python packages).

Required environment:

- `VIBI_API_KEY`: supplier secret, server only.
- `OWNER_ACCESS_TOKEN`: random owner access token, at least 32 characters; use 32 random bytes or more. Never place it in query parameters.
- `PORT`: defaults to 8787. The listener always binds 127.0.0.1.
- `APP_ORIGIN`: exact browser origin, including scheme/port; defaults to http://127.0.0.1:8787. Required when fronted by an HTTPS reverse proxy. Configure the proxy to preserve this Host, and set the origin to HTTPS for Secure cookies. X-Forwarded headers are deliberately not trusted.
- `VOICEGEN_DATA_DIR`: defaults to ~/.local/share/voicegen. Contains private SQLite and audio, outside dist/public; back it up and keep permissions private.
- `VIBI_BASE`: defaults to https://api.vibi.pro/v1.
- `VIBI_AUDIO_HOSTS`: optional comma-separated additional exact HTTPS hostnames. Default audio host is the supplier API hostname. Every resolved address must be globally routable; connections pin a validated address and verify TLS for the original hostname. Redirects are rejected and API keys are never forwarded to audio hosts.

Authentication: frontend reads an owner token from a login link fragment, immediately clears the fragment, then POSTs JSON `{token}` to `/api/session`. This returns an opaque HttpOnly SameSite=Strict 12-hour cookie. The frontend must not persist the owner token. `DELETE /api/session` logs out. Rotating the owner token invalidates existing sessions after restart. `/api/health` is public and reports capabilities only; other APIs require the session. Missing Origin permits non-browser same-host clients; explicit cross-origin mutations and cross-site browser requests are rejected. No CORS permissions are emitted. Static assets are public and must never contain secrets.

Generation contract:

- `POST /api/generate`: existing TTS fields plus mandatory `request_id` (8-128 letters, digits, underscores or hyphens). Returns `{generation}` with id, taskId, requestId, kind, state, text, voiceIds, createdAt/expiresAt (epoch milliseconds), audioUrl, credits, characters, progress, issue. `kind` defaults to `tts`.
- Reuse exactly the same request_id on network retry. The durable unique claim and canonical payload hash prevent duplicate supplier dispatch across concurrent requests and restart. Different payload returns 409. A request is durably marked `uncertain` before sending its only supplier POST. A timeout, 5xx, malformed response, or process crash leaves it uncertain and will NEVER resubmit automatically. It may require manual supplier reconciliation; the frontend must not create a new request ID to auto-retry uncertainty.
- Dialogue uses `kind: dialogue`, `text` in `Name: text` form, a `speakers` map (2-10 entries with voice_id/provider/model_id/language_code/voice_settings), and optional `pause_between_turns` (0-3). At least two configured speakers must occur.
- `GET /api/history`: locally recorded generations only. Does not call supplier-wide history.
- `GET /api/history/:id`: accepts local id or locally allowlisted task id; refreshes supplier detail and safely ingests completed audio. Returns `{generation}`. Unknown/foreign IDs never trigger supplier lookups.
- `GET /api/audio/:id`: authenticated local private audio, byte ranges and HEAD supported. Access expires exactly 24 hours after local submission, even for existing files or range requests. Expired detail is not refreshed. The file may remain on disk; access expiry is not a disk-deletion retention guarantee.
- `GET /api/me`: live supplier profile and wallet with `source: supplier` and label `Supplier credit balance`. No app balance or billing ledger is implied.
- `GET /api/voices?provider=elevenlabs|minimax|capcut`: normalized bounded first-page catalog; includes hasMore. Preview URLs are intentionally disabled, never exposed raw.

Capabilities: TTS/dialogue supported; SRT, voice previews, app billing, multiuser access and production identity management are unavailable. This is a single-owner staging service. No live generation has been tested or purchased by the automated suite.

Verification: `python3 -m unittest discover -s server -p 'test_*.py' -v`. Tests launch the real `node server.mjs` entrypoint and a local mock HTTP supplier with isolated SQLite/audio data. HTTP supplier URLs require the explicit `VIBI_TEST_MODE=1` flag AND the exact loopback host; never enable that flag in staging.
