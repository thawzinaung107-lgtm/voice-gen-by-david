import hashlib
import hmac
import secrets

SCHEME = 'pbkdf2_sha256'
ITERATIONS = 210_000

def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, ITERATIONS)
    return f'{SCHEME}${ITERATIONS}${salt.hex()}${digest.hex()}'

def verify_password(password, stored):
    try:
        scheme, rounds, salt_hex, digest_hex = stored.split('$')
        if scheme != SCHEME: return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(actual.hex(), digest_hex)
    except (AttributeError, TypeError, ValueError):
        return False
