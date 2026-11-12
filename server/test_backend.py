"""Real HTTP integration tests; the supplier is a local mock, never live Vibi."""
import concurrent.futures
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent
AUDIO = b'ID3' + bytes(range(256)) * 8

class Supplier(BaseHTTPRequestHandler):
    submissions = []
    requests = []
    overrides = {}
    guard = threading.Lock()
    def log_message(self, *args):
        pass
    def send(self, body, status=200, content='application/json', extra=None):
        raw = json.dumps(body).encode() if content == 'application/json' else body
        self.send_response(status)
        self.send_header('Content-Type', content)
        self.send_header('Content-Length', str(len(raw)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(raw)
        except BrokenPipeError:
            pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        with sqlite3.connect(self.database) as c:
            claims = c.execute("SELECT COUNT(*) FROM generations WHERE state='uncertain'").fetchone()[0]
            assert claims >= 1, 'Supplier dispatch occurred without a committed uncertainty claim'
        with self.guard:
            self.submissions.append((self.path, body))
            task = 'task_' + str(len(self.submissions))
        # The request really reaches the supplier, then its response times out.
        if body['text'] == 'timeout':
            time.sleep(0.7)
        else:
            time.sleep(0.08)
        self.send({'id': task, 'status': 'pending'}, 202)
    def do_GET(self):
        with self.guard:
            self.requests.append(self.path)
        if self.path == '/v1/auth/me':
            return self.send({'id': 'supplier-owner', 'name': 'Owner', 'email': 'owner@example.test', 'credit_balance': 4321})
        if 'voices' in self.path:
            return self.send({'voices': [{'voice_id': 'voice_one', 'name': 'One', 'language': 'en', 'preview_url': 'https://secret.test/preview'}], 'has_more': False})
        if self.path.startswith('/v1/history/'):
            task = self.path.rsplit('/', 1)[1]
            url = self.overrides.get(task, f'http://127.0.0.1:{self.server.server_port}/media/audio.mp3')
            return self.send({'id': task, 'status': 'completed', 'result': {'audio_url': url}, 'credits_deducted': 12, 'characters_used': 10, 'progress': 100})
        if self.path == '/media/redirect.mp3':
            return self.send(b'', 302, 'audio/mpeg', {'Location': 'http://127.0.0.1:1/forbidden'})
        if self.path == '/media/audio.mp3':
            assert self.headers.get('xi-api-key') is None
            return self.send(AUDIO, content='audio/mpeg')
        self.send({'error': 'unknown'}, 404)

def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

class BackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.supplier = ThreadingHTTPServer(('127.0.0.1', 0), Supplier)
        threading.Thread(target=cls.supplier.serve_forever, daemon=True).start()
        scratch = Path(os.environ.get('TMPDIR', '/root/.hermes/cache/scratch'))
        scratch.mkdir(parents=True, exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(dir=scratch)
        Supplier.database = str(Path(cls.tmp.name) / 'state.sqlite3')
        cls.port = free_port()
        cls.token = 'integration-owner-token-' + 'x' * 40
        cls.env = dict(os.environ, VIBI_API_KEY='mock-secret-no-live-spend', OWNER_ACCESS_TOKEN=cls.token,
                       PORT=str(cls.port), VIBI_BASE=f'http://127.0.0.1:{cls.supplier.server_port}/v1',
                       VOICEGEN_DATA_DIR=cls.tmp.name, VIBI_TEST_MODE='1', VIBI_TIMEOUT='0.25')
        cls.start()
        status, body, headers = cls.request('POST', '/api/session', {'token': cls.token}, auth=False)
        assert status == 200, body
        cls.cookie = headers['set-cookie'].split(';')[0]
    @classmethod
    def start(cls):
        cls.process = subprocess.Popen(['node', 'server.mjs'], cwd=ROOT, env=cls.env,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if cls.process.poll() is not None:
                raise RuntimeError(cls.process.communicate()[1].decode())
            try:
                if cls.request('GET', '/api/health', auth=False)[0] == 200:
                    return
            except OSError:
                pass
            time.sleep(0.03)
        raise RuntimeError('Backend failed startup')
    @classmethod
    def stop(cls):
        cls.process.terminate()
        cls.process.wait(timeout=5)
        cls.process.communicate()
    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.supplier.shutdown()
        cls.supplier.server_close()
        cls.tmp.cleanup()
    @classmethod
    def request(cls, method, path, body=None, headers=None, auth=True):
        h = {'Connection': 'close'}
        if auth:
            h['Cookie'] = cls.cookie
        if body is not None:
            h['Content-Type'] = 'application/json'
        h.update(headers or {})
        c = http.client.HTTPConnection('127.0.0.1', cls.port, timeout=5)
        c.request(method, path, json.dumps(body) if body is not None else None, h)
        r = c.getresponse()
        raw, hs, status = r.read(), dict(r.getheaders()), r.status
        c.close()
        lower = {k.lower(): v for k, v in hs.items()}
        value = json.loads(raw) if lower.get('content-type') == 'application/json' and raw else raw
        return status, value, lower
    def generation(self, request_id, **extra):
        status, body, _ = self.request('POST', '/api/generate', dict(request_id=request_id, text='Hello there', voice_id='voice_one', **extra))
        self.assertIn(status, (200, 202), body)
        return body['generation']
    def test_01_auth_csrf_headers_and_health(self):
        for route in ('/api/me', '/api/voices', '/api/history', '/api/history/foreign', '/api/audio/foreign'):
            status, _, headers = self.request('GET', route, auth=False)
            self.assertEqual(status, 401)
            self.assertEqual(headers['cache-control'], 'private, no-store')
        self.assertEqual(self.request('GET', '/api/health', headers={'Host': 'attacker.invalid'}, auth=False)[0], 403)
        self.assertEqual(self.request('POST', '/api/generate', {}, auth=False)[0], 401)
        self.assertEqual(self.request('POST', '/api/session', {'token': 'wrong'}, auth=False)[0], 401)
        self.assertEqual(self.request('POST', '/api/session', {'token': self.token}, headers={'Origin': 'https://attacker.invalid'}, auth=False)[0], 403)
        self.assertEqual(self.request('POST', '/api/generate', {}, headers={'Origin': 'https://attacker.invalid'})[0], 403)
        self.assertEqual(self.request('POST', '/api/generate', {}, headers={'Sec-Fetch-Site': 'cross-site'})[0], 403)
        status, body, _ = self.request('GET', '/api/health', auth=False)
        self.assertEqual(status, 200)
        self.assertFalse(body['capabilities']['srt'])
        self.assertNotIn('mock-secret', json.dumps(body))
        _, _, headers = self.request('POST', '/api/session', {'token': self.token}, auth=False)
        self.assertIn('HttpOnly', headers['set-cookie'])
        self.assertIn('SameSite=Strict', headers['set-cookie'])
    def test_02_live_balance_and_normalized_voices(self):
        status, body, _ = self.request('GET', '/api/me')
        self.assertEqual(status, 200)
        self.assertEqual(body['wallet']['balance'], 4321)
        self.assertEqual(body['wallet']['source'], 'supplier')
        status, body, _ = self.request('GET', '/api/voices')
        self.assertEqual(status, 200)
        self.assertEqual(len(body['voices']), 1)
        self.assertEqual(body['voices'][0]['id'], 'voice_one')
        self.assertIsNone(body['voices'][0]['preview_url'])
        self.assertNotIn('https://', json.dumps(body))
    def test_03_concurrent_idempotency_conflict_and_restart(self):
        before = len(Supplier.submissions)
        def submit(_):
            return self.generation('concurrent_request_0001')
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            records = list(pool.map(submit, range(12)))
        self.assertEqual(len({r['id'] for r in records}), 1)
        self.assertEqual(len(Supplier.submissions) - before, 1)
        generation = records[0]
        status, _, _ = self.request('POST', '/api/generate', {'request_id': 'concurrent_request_0001', 'text': 'Changed', 'voice_id': 'voice_one'})
        self.assertEqual(status, 409)
        self.stop()
        self.start()
        replay = self.generation('concurrent_request_0001')
        self.assertEqual(replay['id'], generation['id'])
        self.assertEqual(len(Supplier.submissions) - before, 1)
        self.assertEqual(self.request('GET', '/api/history/' + replay['taskId'])[0], 200)
    def test_04_timeout_is_durable_uncertain_and_never_retried(self):
        payload = {'request_id': 'uncertain_request_0001', 'text': 'timeout', 'voice_id': 'voice_one'}
        before = len(Supplier.submissions)
        status, body, _ = self.request('POST', '/api/generate', payload)
        self.assertEqual(status, 202)
        self.assertEqual(body['generation']['state'], 'uncertain')
        self.assertIsNone(body['generation']['taskId'])
        self.stop()
        self.start()
        for _ in range(3):
            status, replay, _ = self.request('POST', '/api/generate', payload)
            self.assertEqual(replay['generation']['id'], body['generation']['id'])
            self.assertEqual(replay['generation']['state'], 'uncertain')
        self.assertEqual(len(Supplier.submissions) - before, 1)
    def test_05_ownership_and_no_supplier_wide_history(self):
        before = len(Supplier.requests)
        self.assertEqual(self.request('GET', '/api/history/not_local_task')[0], 404)
        self.assertEqual(self.request('GET', '/api/audio/not_local_task')[0], 404)
        self.assertEqual(len(Supplier.requests), before)
        g = self.generation('ownership_request_0001')
        with sqlite3.connect(Path(self.tmp.name) / 'state.sqlite3') as c:
            c.execute('UPDATE generations SET owner=? WHERE id=?', ('other-owner', g['id']))
        self.assertEqual(self.request('GET', '/api/history/' + g['taskId'])[0], 404)
        self.assertEqual(self.request('GET', '/api/audio/' + g['id'])[0], 404)
        _, body, _ = self.request('GET', '/api/history')
        self.assertNotIn(g['id'], [x['id'] for x in body['items']])
        self.assertNotIn('/v1/history', Supplier.requests)
    def test_06_private_ingestion_ranges_and_expiry(self):
        g = self.generation('audio_request_0001')
        status, body, _ = self.request('GET', '/api/history/' + g['id'])
        self.assertEqual(status, 200)
        g = body['generation']
        self.assertEqual(g['state'], 'completed')
        self.assertEqual(g['credits'], 12)
        self.assertEqual(g['audioUrl'], '/api/audio/' + g['id'])
        self.assertNotIn('http', json.dumps(g))
        status, audio, headers = self.request('GET', g['audioUrl'])
        self.assertEqual((status, audio), (200, AUDIO))
        self.assertEqual(headers['cache-control'], 'private, no-store')
        for value, expected in [('bytes=2-8', AUDIO[2:9]), ('bytes=-5', AUDIO[-5:]), ('bytes=2000-', AUDIO[2000:])]:
            status, raw, headers = self.request('GET', g['audioUrl'], headers={'Range': value})
            self.assertEqual(status, 206)
            self.assertEqual(raw, expected)
            self.assertIn('content-range', headers)
        for value in ('bytes=99999-', 'bytes=8-2', 'bytes=0-1,3-4', 'bytes=-0'):
            self.assertEqual(self.request('GET', g['audioUrl'], headers={'Range': value})[0], 416)
        before = len(Supplier.requests)
        self.assertEqual(self.request('GET', g['audioUrl'], auth=False)[0], 401)
        with sqlite3.connect(Path(self.tmp.name) / 'state.sqlite3') as c:
            c.execute('UPDATE generations SET created=? WHERE id=?', (int(time.time() * 1000) - 86400001, g['id']))
        self.assertEqual(self.request('GET', g['audioUrl'])[0], 410)
        self.assertEqual(self.request('GET', g['audioUrl'], headers={'Range': 'bytes=0-1'})[0], 410)
        _, body, _ = self.request('GET', '/api/history/' + g['taskId'])
        self.assertEqual(body['generation']['state'], 'expired')
        self.assertIsNone(body['generation']['audioUrl'])
        self.assertEqual(len(Supplier.requests), before)
    def test_07_ssrf_and_redirect_denied(self):
        urls = ['http://169.254.169.254/latest/meta-data', 'https://localhost/audio.mp3', 'https://api.vibi.pro.evil.test/audio.mp3',
                'file:///etc/passwd', f'http://user:pass@127.0.0.1:{self.supplier.server_port}/media/audio.mp3',
                f'http://127.0.0.1:{self.supplier.server_port}/media/redirect.mp3']
        for i, url in enumerate(urls):
            g = self.generation(f'unsafe_audio_request_{i:04d}')
            Supplier.overrides[g['taskId']] = url
            _, body, _ = self.request('GET', '/api/history/' + g['id'])
            self.assertIsNone(body['generation']['audioUrl'])
            self.assertEqual(body['generation']['issue'], 'Audio could not be safely retrieved')
            self.assertEqual(self.request('GET', '/api/audio/' + g['id'])[0], 404)
    def test_08_validation_paths_and_dialogue_dispatch(self):
        for path in ('/%2e%2e/server/backend.py', '/assets/%2e%2e/%2e%2e/server.mjs', '/%252e%252e/server.mjs', '/api/history/a%2fb', '/%00', '/server.mjs', '/state.sqlite3'):
            self.assertIn(self.request('GET', path)[0], (400, 404))
        before = len(Supplier.submissions)
        for payload in ({}, {'request_id': 'valid_request_1234', 'text': 'Hi', 'voice_id': '../escape'},
                        {'request_id': 'valid_request_1234', 'text': 'Hi', 'voice_id': 'safe', 'voice_settings': {'speed': 100}},
                        {'request_id': 'valid_request_1234', 'text': 'Hi', 'voice_id': 'safe', 'kind': 'srt'}):
            self.assertIn(self.request('POST', '/api/generate', payload)[0], (400, 422))
        self.assertEqual(len(Supplier.submissions), before)
        body = {'request_id': 'dialogue_request_0001', 'kind': 'dialogue', 'text': 'Alice: Hello\nBob: Hi',
                'speakers': {'Alice': {'voice_id': 'voice_one'}, 'Bob': {'voice_id': 'voice_two', 'provider': 'minimax', 'language_code': 'English'}}, 'pause_between_turns': 0.5}
        status, response, _ = self.request('POST', '/api/generate', body)
        self.assertEqual(status, 202)
        self.assertEqual(response['generation']['kind'], 'dialogue')
        self.assertEqual(response['generation']['voiceIds'], ['voice_one', 'voice_two'])
        route, forwarded = Supplier.submissions[-1]
        self.assertEqual(route, '/v1/dialogue')
        self.assertEqual(forwarded['pause_between_turns'], 0.5)
        self.assertEqual(forwarded['speakers']['Bob']['provider'], 'minimax')
        self.assertNotIn('request_id', forwarded)

    def test_09_logout_expired_sessions_and_login_throttle(self):
        status, _, headers = self.request('POST', '/api/session', {'token': self.token}, auth=False)
        self.assertEqual(status, 200)
        cookie = headers['set-cookie'].split(';')[0]
        self.assertEqual(self.request('DELETE', '/api/session', headers={'Cookie': cookie})[0], 200)
        self.assertEqual(self.request('GET', '/api/history', headers={'Cookie': cookie})[0], 401)
        status, _, headers = self.request('POST', '/api/session', {'token': self.token}, auth=False)
        cookie = headers['set-cookie'].split(';')[0]
        with sqlite3.connect(Path(self.tmp.name) / 'state.sqlite3') as c:
            c.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.request('GET', '/api/history', headers={'Cookie': cookie})[0], 401)
        statuses = [self.request('POST', '/api/session', {'token': 'wrong'}, auth=False)[0] for _ in range(21)]
        self.assertIn(429, statuses)

if __name__ == '__main__':
    unittest.main(verbosity=2)
