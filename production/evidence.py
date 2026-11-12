import logging
import re
import struct

log = logging.getLogger('voicegen.evidence')

# Markers that indicate an active-content polyglot hiding in file data.
_ACTIVE = re.compile(rb'<\s*script|<\s*iframe|javascript\s*:', re.IGNORECASE)
_PDF_DANGER = re.compile(rb'/JS\b|/JavaScript\b|/Launch\b|/OpenAction\b|/AA\b', re.IGNORECASE)

def _png_ok(data):
    if not data.startswith(b'\x89PNG\r\n\x1a\n'): return False
    # Walk chunks: need IHDR first and at least one IDAT before IEND.
    pos, seen_ihdr, seen_idat = 8, False, False
    while pos + 12 <= len(data):
        length, ctype = struct.unpack('>I4s', data[pos:pos + 8])
        if ctype == b'IHDR':
            if pos != 8: return False
            seen_ihdr = True
        elif ctype == b'IDAT': seen_idat = True
        elif ctype == b'IEND': break
        pos += 12 + length
    if not (seen_ihdr and seen_idat): return False
    # Polyglot check: no active markup anywhere in the byte stream.
    return not _ACTIVE.search(data)

def _jpeg_ok(data):
    return data.startswith(b'\xff\xd8\xff') and data.rstrip().endswith(b'\xff\xd9')

def _pdf_ok(data):
    if not data.startswith(b'%PDF-'): return False
    if b'%%EOF' not in data[-4096:]: return False
    return not _PDF_DANGER.search(data)

_CHECKS = {'image/png': _png_ok, 'image/jpeg': _jpeg_ok, 'application/pdf': _pdf_ok}

def validate(content_type, data, user=None, topup=None):
    """Return True if the upload passes structural + active-content checks."""
    check = _CHECKS.get(content_type)
    ok = bool(check and check(bytes(data)))
    if not ok:
        log.warning('evidence rejected', extra={'user_id': str(user), 'topup_id': str(topup), 'content_type': content_type, 'size': len(data)})
    return ok
