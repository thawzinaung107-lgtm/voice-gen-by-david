import { spawn } from 'node:child_process';
import { createServer } from 'node:http';

const PORT = Number(process.env.AUDIO_PORT || 8791);
const MAX = 5000;
const VOICES = { roger: 38, brian: 28, daniel: 48, adam: 62, lily: 72 };

function speak(text, voice, speed) {
  const pitch = VOICES[voice] ?? 42;
  const rate = Math.round(140 * (Number(speed) || 1));
  return new Promise((resolve, reject) => {
    const child = spawn('espeak-ng', ['-v', 'en-us', '-s', String(rate), '-p', String(pitch), '--stdout', text], { stdio: ['ignore', 'pipe', 'pipe'] });
    const chunks = [];
    let stderr = '';
    child.stdout.on('data', chunk => chunks.push(chunk));
    child.stderr.on('data', chunk => { stderr += chunk; });
    child.on('error', reject);
    child.on('close', code => code === 0 ? resolve(Buffer.concat(chunks)) : reject(new Error(stderr || `espeak exited ${code}`)));
  });
}

function concatWav(buffers) {
  if (buffers.length === 1) return buffers[0];
  const silence = Buffer.alloc(22050 * 2 * 0.28);
  const parts = [];
  buffers.forEach((buffer, index) => {
    parts.push(buffer.subarray(44));
    if (index < buffers.length - 1) parts.push(silence);
  });
  const data = Buffer.concat(parts);
  const out = Buffer.from(buffers[0].subarray(0, 44));
  const joined = Buffer.concat([out, data]);
  joined.writeUInt32LE(36 + data.length, 4);
  joined.writeUInt32LE(data.length, 40);
  return joined;
}

createServer(async (req, res) => {
  if (req.method !== 'POST' || new URL(req.url, 'http://local').pathname !== '/audio') {
    res.writeHead(404).end();
    return;
  }
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  let body;
  try { body = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { res.writeHead(400).end(); return; }
  const speed = body.speed;
  const lines = Array.isArray(body.lines) && body.lines.length
    ? body.lines.map(line => ({ text: String(line.text || '').trim(), voice: line.voice })).filter(line => line.text)
    : [{ text: String(body.text || '').replace(/^[AB]\s*[:：]\s*/gm, '').trim(), voice: body.voice }];
  const clipped = [];
  let used = 0;
  for (const line of lines) {
    const text = line.text.slice(0, MAX - used);
    if (!text) break;
    clipped.push({ text, voice: line.voice });
    used += text.length;
  }
  if (!clipped.length) { res.writeHead(400).end(); return; }
  try {
    const wavs = [];
    for (const line of clipped) wavs.push(await speak(line.text, line.voice, speed));
    const wav = concatWav(wavs);
    res.writeHead(200, { 'Content-Type': 'audio/wav', 'Cache-Control': 'no-store' });
    res.end(wav);
  } catch {
    res.writeHead(502).end();
  }
}).listen(PORT, '127.0.0.1');