// Keep the documented Node entrypoint; the backend uses Python's bundled SQLite.
import { spawn } from 'node:child_process';
const child = spawn('python3', [new URL('./server/backend.py', import.meta.url).pathname], { stdio: 'inherit', env: process.env });
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
child.on('exit', (code) => process.exit(code ?? 1));
