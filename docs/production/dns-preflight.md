# Read-only DNS preflight

`python3 scripts/production-dns-preflight.py` invokes `dig` for zone NS/TXT and hostname A/AAAA/TXT, records UTC time and preserves DNS response status. It performs no writes, account login, ACME issuance or provisioning. NXDOMAIN is a successful DNS query reporting an absent name, not evidence that deployment is ready.

Observed on 2026-11-10: `atbd.space` NS answers were `launch1.spaceship.net.` and `launch2.spaceship.net.`; `voicegen.atbd.space` A/AAAA/TXT returned NXDOMAIN; zone TXT had no answer. Results can change and should be rerun before any decision. **Domain ownership is unknown**: nameservers and resolving records never establish who can authorize changes.

Before a separately authorized public rollout, the owner must demonstrate registrar/authoritative-zone control using account access or an independently approved TXT challenge. Record intended host, target IP, current zone export, TTL and rollback values. Review existing Caddy sites/ports without overwriting them; validate an isolated config first. Only explicit approval permits adding DNS, opening ports or activating TLS. The Caddy template is a proposed host configuration and was validated without starting a public server.
