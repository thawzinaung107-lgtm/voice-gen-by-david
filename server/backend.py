"""Single-owner staging backend. No supplier-wide history or submission retries."""
import hashlib
import hmac
import http.client
import ipaddress
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import ssl
import threading
import time
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent.parent
os.umask(0o077)
DATA = Path(os.environ.get('VOICEGEN_DATA_DIR', str(Path.home() / '.local/share/voicegen'))).resolve()
if DATA == ROOT or ROOT / 'dist' in DATA.parents or ROOT / 'public' in DATA.parents or DATA in (ROOT / 'dist', ROOT / 'public'):
    raise RuntimeError('Data directory must be outside public assets')
DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
DB = DATA / 'state.sqlite3'
PORT = int(os.environ.get('PORT', '8787'))
BASE = os.environ.get('VIBI_BASE', 'https://api.vibi.pro/v1').rstrip('/')
KEY = os.environ.get('VIBI_API_KEY', '')
TOKEN = os.environ.get('OWNER_ACCESS_TOKEN', '')
ORIGIN = os.environ.get('APP_ORIGIN', f'http://127.0.0.1:{PORT}').rstrip('/')
TIMEOUT = float(os.environ.get('VIBI_TIMEOUT', '20'))
TEST = os.environ.get('VIBI_TEST_MODE') == '1'
BASE_URL = urllib.parse.urlsplit(BASE)
if not KEY or len(TOKEN) < 32:
    raise RuntimeError('VIBI_API_KEY and OWNER_ACCESS_TOKEN (at least 32 characters) required')
if BASE_URL.scheme != 'https' and not (TEST and BASE_URL.scheme == 'http' and BASE_URL.hostname == '127.0.0.1'):
    raise RuntimeError('Supplier must use HTTPS (loopback HTTP permitted only in test mode)')
if BASE_URL.username or BASE_URL.password or BASE_URL.query or BASE_URL.fragment:
    raise RuntimeError('Invalid supplier base')
OWNER = 'single-owner'
LOCK = threading.RLock()
LOGIN_LOCK = threading.Lock()
LOGIN_ATTEMPTS = []
SESSION_EPOCH = hashlib.sha256(TOKEN.encode()).hexdigest()

def db():
    c = sqlite3.connect(DB, timeout=15)
    c.row_factory = sqlite3.Row
    return c

with db() as c:
    c.execute('PRAGMA journal_mode=WAL')
    c.executescript('''CREATE TABLE IF NOT EXISTS generations (
      id TEXT PRIMARY KEY, owner TEXT NOT NULL, request_id TEXT NOT NULL UNIQUE,
      payload_hash TEXT NOT NULL, payload TEXT NOT NULL, kind TEXT NOT NULL,
      task_id TEXT UNIQUE, state TEXT NOT NULL, created INTEGER NOT NULL,
      credits REAL, characters INTEGER, progress REAL, audio_file TEXT, issue TEXT);
      CREATE TABLE IF NOT EXISTS sessions (hash TEXT PRIMARY KEY, epoch TEXT NOT NULL, expires INTEGER NOT NULL);''')

def now():
    return int(time.time() * 1000)

class ApiError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message

def clean_string(value, maximum=200):
    return isinstance(value, str) and 0 < len(value) <= maximum and not any(ord(x) < 32 for x in value)

def numeric(value, low, high):
    return type(value) in (int, float) and low <= value <= high

def config(body, dialogue=False):
    if not isinstance(body, dict):
        raise ApiError(400, 'Invalid voice configuration')
    provider = body.get('provider', 'elevenlabs')
    if provider not in ('elevenlabs', 'minimax', 'capcut'):
        raise ApiError(400, 'Invalid provider')
    voice = body.get('voice_id')
    if not isinstance(voice, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', voice):
        raise ApiError(400, 'Invalid voice_id')
    lang = body.get('language_code', 'en')
    if not clean_string(lang, 80) or lang == 'auto':
        raise ApiError(400, 'Invalid language_code')
    model = body.get('model_id') or {'elevenlabs': 'eleven_multilingual_v2', 'minimax': 'speech-2.8-turbo', 'capcut': 'capcut'}[provider]
    if not clean_string(model, 100):
        raise ApiError(400, 'Invalid model_id')
    settings = body.get('voice_settings', {})
    if not isinstance(settings, dict):
        raise ApiError(400, 'Invalid voice_settings')
    limits = {'speed': (0.7, 1.2)} if provider == 'elevenlabs' else {'speed': (0.5, 2), 'pitch': (-12, 12)}
    if provider == 'elevenlabs':
        limits.update({k: (0, 1) for k in ('stability', 'similarity_boost', 'style')})
    if provider == 'minimax':
        limits['vol'] = (0.01, 10)
    for k, v in settings.items():
        if k == 'use_speaker_boost' and provider == 'elevenlabs' and type(v) is bool:
            continue
        if k not in limits or not numeric(v, *limits[k]) or (k == 'pitch' and type(v) is not int):
            raise ApiError(400, 'Invalid voice setting')
    return dict(voice_id=voice, provider=provider, model_id=model, language_code=lang, voice_settings=settings)

def validate(body):
    if not isinstance(body, dict):
        raise ApiError(400, 'JSON object required')
    request_id = body.get('request_id')
    if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,128}', request_id):
        raise ApiError(400, 'request_id required (8-128 letters, digits, _ or -)')
    text = body.get('text')
    if not isinstance(text, str) or not text.strip() or len(text) > 20000:
        raise ApiError(400, 'text required (maximum 20000 characters)')
    if body.get('export_transcript') or body.get('kind') == 'srt':
        raise ApiError(422, 'SRT is not available in this staging backend')
    kind = body.get('kind', 'tts')
    if kind == 'tts':
        payload = config(body)
        voice = payload.pop('voice_id')
        payload['text'] = text
        payload['export_transcript'] = False
        route = '/text-to-speech/' + voice
        stored = dict(payload, voice_id=voice)
    elif kind == 'dialogue':
        speakers = body.get('speakers')
        if not isinstance(speakers, dict) or not 2 <= len(speakers) <= 10:
            raise ApiError(400, 'Dialogue needs 2-10 speakers')
        used = set()
        for line in text.splitlines():
            if ':' in line:
                name = line.split(':', 1)[0].strip()
                if name not in speakers:
                    raise ApiError(400, 'Unknown dialogue speaker')
                used.add(name)
        if len(used) < 2 or any(not clean_string(n, 60) or ':' in n for n in speakers):
            raise ApiError(400, 'At least two configured speakers must appear')
        pause = body.get('pause_between_turns', 0)
        if not numeric(pause, 0, 3):
            raise ApiError(400, 'Invalid pause_between_turns')
        payload = dict(text=text, speakers={n: config(v, True) for n, v in speakers.items()}, pause_between_turns=pause)
        stored, route = payload, '/dialogue'
    else:
        raise ApiError(400, 'Invalid generation kind')
    canonical = json.dumps(dict(kind=kind, payload=stored), sort_keys=True, separators=(',', ':'), allow_nan=False)
    return request_id, kind, payload, stored, route, hashlib.sha256(canonical.encode()).hexdigest()

def request_supplier(route, payload=None):
    conn_cls = http.client.HTTPSConnection if BASE_URL.scheme == 'https' else http.client.HTTPConnection
    conn = conn_cls(BASE_URL.hostname, BASE_URL.port, timeout=TIMEOUT)
    try:
        conn.request('POST' if payload is not None else 'GET', BASE_URL.path + route,
                     body=json.dumps(payload).encode() if payload is not None else None,
                     headers={'xi-api-key': KEY, 'Content-Type': 'application/json', 'Accept': 'application/json'})
        r = conn.getresponse()
        raw = r.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('Oversize supplier response')
        return r.status, json.loads(raw)
    finally:
        conn.close()

def get_supplier(route):
    try:
        status, body = request_supplier(route)
        if status != 200 or not isinstance(body, (dict, list)):
            raise ValueError('Supplier error')
        return body
    except Exception:
        raise ApiError(502, 'Supplier temporarily unavailable')

def find(identifier):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', identifier):
        raise ApiError(404, 'Generation not found')
    with db() as c:
        row = c.execute('SELECT * FROM generations WHERE owner=? AND (id=? OR task_id=?)', (OWNER, identifier, identifier)).fetchone()
    if row is None:
        raise ApiError(404, 'Generation not found')
    return row

def expired(row):
    return now() >= row['created'] + 86400000

def normalized(row):
    p = json.loads(row['payload'])
    is_expired = expired(row)
    return dict(id=row['id'], taskId=row['task_id'], requestId=row['request_id'], kind=row['kind'],
                state='expired' if is_expired else row['state'], text=p['text'],
                voiceIds=[p['voice_id']] if row['kind'] == 'tts' else list(dict.fromkeys(v['voice_id'] for v in p['speakers'].values())),
                createdAt=row['created'], expiresAt=row['created'] + 86400000,
                audioUrl=f"/api/audio/{row['id']}" if row['audio_file'] and not is_expired else None,
                credits=row['credits'], characters=row['characters'], progress=row['progress'],
                issue=row['issue'])

class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname, address, port):
        super().__init__(hostname, port, timeout=TIMEOUT)
        self.address = address
    def connect(self):
        sock = socket.create_connection((self.address, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)

def ingest(url, local_id):
    """Exact host allowlist, public address pinning, TLS SNI, no redirects/key forwarding."""
    u = urllib.parse.urlsplit(url)
    allowed = {BASE_URL.hostname} | {h.strip().lower() for h in os.environ.get('VIBI_AUDIO_HOSTS', '').split(',') if h.strip()}
    local_test = TEST and u.hostname == '127.0.0.1' and u.port == BASE_URL.port and u.scheme == 'http'
    if (not local_test and (u.scheme != 'https' or u.port not in (None, 443))) or u.hostname not in allowed or u.username or u.password or u.fragment:
        raise ValueError('Unsafe audio URL')
    if not u.path.startswith('/') or any(ord(x) < 32 for x in url):
        raise ValueError('Unsafe audio URL')
    if local_test:
        conn = http.client.HTTPConnection(u.hostname, u.port, timeout=TIMEOUT)
    else:
        addresses = {item[4][0] for item in socket.getaddrinfo(u.hostname, 443, type=socket.SOCK_STREAM)}
        if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
            raise ValueError('Non-public audio address')
        conn = PinnedHTTPS(u.hostname, sorted(addresses)[0], 443)
    partial = DATA / (local_id + '.' + secrets.token_hex(8) + '.part')
    target = DATA / (local_id + '.mp3')
    try:
        conn.request('GET', urllib.parse.urlunsplit(('', '', u.path, u.query, '')), headers={'Accept': 'audio/*'})
        r = conn.getresponse()
        if r.status != 200 or r.getheader('Content-Type', '').split(';')[0] not in ('audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav', 'audio/ogg', 'audio/mp4', 'application/octet-stream'):
            raise ValueError('Invalid audio response')
        size = 0
        with partial.open('xb') as f:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > 50_000_000:
                    raise ValueError('Audio too large')
                f.write(chunk)
        if size == 0:
            raise ValueError('Empty audio')
        os.replace(partial, target)
        return target.name
    finally:
        conn.close()
        partial.unlink(missing_ok=True)

def refresh(row):
    if expired(row) or not row['task_id'] or row['state'] == 'failed' or row['audio_file']:
        return row
    t = get_supplier('/history/' + urllib.parse.quote(row['task_id'], safe=''))
    if not isinstance(t, dict) or t.get('id') != row['task_id']:
        raise ApiError(502, 'Supplier detail mismatch')
    state = {'pending': 'queued', 'processing': 'processing', 'completed': 'completed', 'failed': 'failed'}.get(t.get('status'), row['state'])
    audio, issue = None, None
    result = t.get('result')
    if state == 'completed' and isinstance(result, dict) and isinstance(result.get('audio_url'), str):
        try:
            audio = ingest(result['audio_url'], row['id'])
        except Exception:
            issue = 'Audio could not be safely retrieved'
    def number(k):
        v = t.get(k)
        return v if numeric(v, 0, 1e12) else None
    with db() as c:
        c.execute('UPDATE generations SET state=?,audio_file=COALESCE(audio_file,?),issue=?,credits=?,characters=?,progress=? WHERE id=?',
                  (state, audio, issue, number('credits_deducted'), number('characters_used'), number('progress'), row['id']))
    return find(row['id'])

class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *args):
        pass  # Never log tokens, payloads, supplier responses, or signed URLs.
    def headers_common(self):
        self.send_header('Cache-Control', 'private, no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
    def respond(self, status, value, headers=None):
        # Close even rejected requests: their unread body must not become another request.
        self.close_connection = True
        raw = json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Connection', 'close')
        self.headers_common()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(raw)
    def body(self):
        if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            raise ApiError(415, 'application/json required')
        try:
            size = int(self.headers.get('Content-Length', '-1'))
            if not 0 <= size <= 100000:
                raise ValueError()
            return json.loads(self.rfile.read(size), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except Exception:
            self.close_connection = True
            raise ApiError(400, 'Invalid or oversized JSON body')
    def authorize(self):
        try:
            cookies = SimpleCookie(self.headers.get('Cookie', ''))
            sid = cookies['voicegen_session'].value
            digest = hashlib.sha256(sid.encode()).hexdigest()
            with db() as c:
                session = c.execute('SELECT expires FROM sessions WHERE hash=? AND epoch=?', (digest, SESSION_EPOCH)).fetchone()
            if not session or session['expires'] <= now():
                raise ValueError()
        except Exception:
            raise ApiError(401, 'Owner session required')
    def mutation_origin(self):
        if self.headers.get('Sec-Fetch-Site') == 'cross-site' or self.headers.get('Origin') not in (None, ORIGIN):
            raise ApiError(403, 'Cross-origin mutation denied')
    def serve(self):
        self.connection.settimeout(30)
        try:
            allowed_hosts = {urllib.parse.urlsplit(ORIGIN).netloc, f'127.0.0.1:{PORT}', f'localhost:{PORT}'}
            if self.headers.get('Host', '') not in allowed_hosts:
                raise ApiError(403, 'Unrecognized request host')
            rawpath = urllib.parse.urlsplit(self.path).path
            path = urllib.parse.unquote(rawpath, errors='strict')
            if not path.startswith('/') or '\\' in path or '\x00' in path or any(x in ('.', '..') for x in path.split('/')) or '%' in path:
                raise ApiError(400, 'Invalid path')
            if self.command not in ('GET', 'HEAD', 'POST', 'DELETE'):
                raise ApiError(405, 'Method not allowed')
            if self.command in ('POST', 'DELETE'):
                self.mutation_origin()
            if path == '/api/health' and self.command in ('GET', 'HEAD'):
                return self.respond(200, dict(ok=True, mode='single-owner-staging', capabilities=dict(tts=True, dialogue=True, srt=False, billing=False, multiuser=False)))
            if path == '/api/session' and self.command == 'POST':
                with LOGIN_LOCK:
                    LOGIN_ATTEMPTS[:] = [t for t in LOGIN_ATTEMPTS if t > time.monotonic() - 60]
                    if len(LOGIN_ATTEMPTS) >= 20:
                        raise ApiError(429, 'Too many login attempts; wait one minute')
                    LOGIN_ATTEMPTS.append(time.monotonic())
                b = self.body()
                if not isinstance(b, dict) or not isinstance(b.get('token'), str) or not hmac.compare_digest(b['token'], TOKEN):
                    raise ApiError(401, 'Invalid owner token')
                sid = secrets.token_urlsafe(48)
                with db() as c:
                    c.execute('DELETE FROM sessions WHERE expires<=? OR epoch<>?', (now(), SESSION_EPOCH))
                    c.execute('INSERT INTO sessions VALUES (?,?,?)', (hashlib.sha256(sid.encode()).hexdigest(), SESSION_EPOCH, now() + 43200000))
                secure = '; Secure' if ORIGIN.startswith('https://') else ''
                return self.respond(200, {'authenticated': True, 'mode': 'single-owner-staging'}, {'Set-Cookie': f'voicegen_session={sid}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200{secure}'})
            if path.startswith('/api/'):
                self.authorize()
                if path == '/api/session' and self.command == 'DELETE':
                    cookies = SimpleCookie(self.headers.get('Cookie', ''))
                    with db() as c:
                        c.execute('DELETE FROM sessions WHERE hash=?', (hashlib.sha256(cookies['voicegen_session'].value.encode()).hexdigest(),))
                    return self.respond(200, {'authenticated': False}, {'Set-Cookie': 'voicegen_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'})
                if path == '/api/me' and self.command in ('GET', 'HEAD'):
                    p = get_supplier('/auth/me')
                    balance = p.get('credit_balance')
                    if not numeric(balance, 0, 1e15):
                        raise ApiError(502, 'Invalid supplier balance')
                    return self.respond(200, {'user': {'id': p.get('id'), 'email': p.get('email'), 'displayName': p.get('name'), 'credits': balance}, 'wallet': {'balance': balance, 'source': 'supplier', 'label': 'Supplier credit balance'}, 'mode': 'single-owner-staging'})
                if path == '/api/voices' and self.command in ('GET', 'HEAD'):
                    voices, pages = {}, []
                    query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                    provider = query.get('provider', ['elevenlabs'])[0]
                    endpoints = {'elevenlabs': ['/default-voices?page_size=30', '/shared-voices?page_size=30&sort=trending'], 'minimax': ['/minimax/system-voices?page=1&page_size=30'], 'capcut': ['/capcut/system-voices?page=1&page_size=30']}
                    if provider not in endpoints:
                        raise ApiError(400, 'Invalid provider')
                    for endpoint in endpoints[provider]:
                        p = get_supplier(endpoint)
                        vs = p.get('voices', p.get('voice_list', []))
                        pages.append(bool(p.get('has_more')))
                        for v in vs:
                            vid = v.get('voice_id')
                            if not isinstance(vid, str):
                                continue
                            labels = {k: v[k] for k in ('gender', 'age', 'accent', 'language', 'use_case') if isinstance(v.get(k), str)}
                            voices[vid] = {'id': vid, 'name': v.get('name', v.get('voice_name', vid)), 'provider': provider, 'labels': labels, 'preview_url': None}
                    return self.respond(200, {'voices': list(voices.values()), 'hasMore': any(pages), 'previewAvailable': False})
                if path == '/api/generate' and self.command == 'POST':
                    request_id, kind, payload, stored, route, digest = validate(self.body())
                    local_id = 'gen_' + secrets.token_hex(16)
                    # BEGIN IMMEDIATE + UNIQUE request_id serializes concurrent dispatch claims.
                    with db() as c:
                        c.execute('BEGIN IMMEDIATE')
                        old = c.execute('SELECT * FROM generations WHERE request_id=?', (request_id,)).fetchone()
                        if old:
                            if old['owner'] != OWNER:
                                raise ApiError(409, 'request_id is unavailable')
                            if old['payload_hash'] != digest:
                                raise ApiError(409, 'request_id was already used with a different payload')
                            return self.respond(200, {'generation': normalized(old), 'replayed': True})
                        c.execute('INSERT INTO generations (id,owner,request_id,payload_hash,payload,kind,state,created) VALUES (?,?,?,?,?,?,?,?)',
                                  (local_id, OWNER, request_id, digest, json.dumps(stored), kind, 'uncertain', now()))
                    # Any crash/timeout after the durable claim remains uncertain; never dispatch again.
                    try:
                        status, result = request_supplier(route, payload)
                        task = result.get('id') if isinstance(result, dict) else None
                        if status == 202 and isinstance(task, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,200}', task):
                            with db() as c:
                                c.execute('UPDATE generations SET task_id=?,state=? WHERE id=?', (task, 'queued', local_id))
                        elif 400 <= status < 500 and status not in (408, 429):
                            with db() as c:
                                c.execute('UPDATE generations SET state=?,issue=? WHERE id=?', ('failed', 'Supplier rejected the request', local_id))
                    except Exception:
                        pass
                    row = find(local_id)
                    return self.respond(202, {'generation': normalized(row)})
                if path == '/api/history' and self.command in ('GET', 'HEAD'):
                    with db() as c:
                        rows = c.execute('SELECT * FROM generations WHERE owner=? ORDER BY created DESC', (OWNER,)).fetchall()
                    return self.respond(200, {'items': [normalized(r) for r in rows]})
                if path.startswith('/api/history/') and self.command in ('GET', 'HEAD'):
                    with LOCK:
                        row = refresh(find(path[len('/api/history/'):]))
                    return self.respond(200, {'generation': normalized(row)})
                if path.startswith('/api/audio/') and self.command in ('GET', 'HEAD'):
                    row = find(path[len('/api/audio/'):])
                    if expired(row):
                        raise ApiError(410, 'Audio expired 24 hours after submission')
                    if not row['audio_file']:
                        raise ApiError(404, 'Audio not available')
                    fp = (DATA / row['audio_file']).resolve()
                    if fp.parent != DATA or not fp.is_file():
                        raise ApiError(404, 'Audio not available')
                    return self.file(fp, audio=True)
                raise ApiError(404, 'API route not found')
            if self.command not in ('GET', 'HEAD'):
                raise ApiError(405, 'Method not allowed')
            root = (ROOT / 'dist').resolve()
            fp = (root / path.lstrip('/')).resolve()
            if fp != root and root not in fp.parents:
                raise ApiError(400, 'Invalid path')
            if path == '/':
                fp = root / 'index.html'
            if not fp.is_file():
                raise ApiError(404, 'File not found')
            return self.file(fp)
        except ApiError as e:
            self.respond(e.status, {'error': e.message})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            self.respond(500, {'error': 'Internal server error'})
    def file(self, fp, audio=False):
        size = fp.stat().st_size
        start, end, status = 0, size - 1, 200
        range_header = self.headers.get('Range') if audio else None
        if range_header:
            m = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header)
            if not m or not any(m.groups()) or size == 0:
                return self.respond(416, {'error': 'Invalid range'}, {'Content-Range': f'bytes */{size}'})
            a, b = m.groups()
            if a:
                start, end = int(a), min(int(b) if b else size - 1, size - 1)
            else:
                start, end = max(0, size - int(b)), size - 1
                if int(b) == 0:
                    start = size
            if start >= size or start > end:
                return self.respond(416, {'error': 'Unsatisfiable range'}, {'Content-Range': f'bytes */{size}'})
            status = 206
        self.send_response(status)
        self.headers_common()
        self.send_header('Content-Type', 'audio/mpeg' if audio else mimetypes.guess_type(fp)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(max(0, end - start + 1)))
        if audio:
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Disposition', 'inline; filename="generation.mp3"')
        if status == 206:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        if self.command != 'HEAD':
            with fp.open('rb') as f:
                f.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
    do_GET = do_HEAD = do_POST = do_DELETE = do_PUT = do_OPTIONS = serve

if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    server.daemon_threads = True
    print(f'Voicegen single-owner staging listening on 127.0.0.1:{PORT}', flush=True)
    server.serve_forever()
