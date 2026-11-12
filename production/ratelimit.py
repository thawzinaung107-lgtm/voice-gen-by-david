import os
import threading
import time
from fastapi import HTTPException

class SlidingWindowLimiter:
    """In-memory per-key sliding-window rate limiter. V1 single-process only."""
    def __init__(self, env=None):
        env = dict(os.environ if env is None else env)
        self._buckets = {}
        self._lock = threading.Lock()
        self.limits = {
            'SESSION': int(env.get('RATE_LIMIT_SESSION_PER_MINUTE', 10)),
            'GENERATE': int(env.get('RATE_LIMIT_GENERATE_PER_MINUTE', 20)),
            'EVIDENCE': int(env.get('RATE_LIMIT_EVIDENCE_PER_MINUTE', 5)),
            'TOPUP': int(env.get('RATE_LIMIT_TOPUP_PER_MINUTE', 10)),
            'ADMIN': int(env.get('RATE_LIMIT_ADMIN_PER_MINUTE', 30)),
        }

    def check(self, name, key):
        limit = self.limits[name]
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.setdefault(name, {})
            hits = bucket.get(key, [])
            hits = [t for t in hits if now - t < 60.0]
            if len(hits) >= limit:
                retry = int(60.0 - (now - hits[0])) + 1
                bucket[key] = hits
                raise HTTPException(429, 'Rate limit exceeded', headers={'Retry-After': str(max(1, retry))})
            hits.append(now)
            bucket[key] = hits
            # Bound memory: drop idle keys opportunistically.
            if len(bucket) > 10000:
                stale = [k for k, v in bucket.items() if not v or now - v[-1] >= 60.0]
                for k in stale: bucket.pop(k, None)
