import json
import logging
import re

# Fields that must never reach log output (tokens, cookies, evidence bytes).
_SCRUB = re.compile(r'(access_token|authorization|cookie|set-cookie|__host-voicegen_session|evidence_body|password)', re.IGNORECASE)

class JsonFormatter(logging.Formatter):
    def format(self, record):
        message = record.getMessage()
        if _SCRUB.search(message):
            message = _SCRUB.sub('[redacted]', message)
        out = {
            'timestamp': self.formatTime(record, '%Y-%m-%dT%H:%M:%S%z'),
            'level': record.levelname,
            'logger': record.name,
            'message': message,
        }
        for key in ('request_id', 'user_id', 'path', 'method', 'status_code', 'duration_ms'):
            value = getattr(record, key, None)
            if value is not None: out[key] = value
        if record.exc_info:
            out['exception'] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)

def configure():
    """Idempotent JSON logging setup for the production app."""
    root = logging.getLogger()
    if getattr(configure, '_done', False): return root
    configure._done = True
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    return root
