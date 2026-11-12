#!/usr/bin/env python3
"""Launch local staging without exposing secrets in argv or frontend assets."""
import json
import os
from pathlib import Path

config = Path.home() / '.config/voicegen/staging.json'
if not config.is_file():
    raise SystemExit('Missing private staging config: ~/.config/voicegen/staging.json')
if config.stat().st_mode & 0o077:
    raise SystemExit('Staging configuration must have mode 0600')
env = dict(os.environ)
env.update(json.loads(config.read_text()))
os.chdir(Path(__file__).resolve().parents[1])
os.execvpe('node', ['node', 'server.mjs'], env)
