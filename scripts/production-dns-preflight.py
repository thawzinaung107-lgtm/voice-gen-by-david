#!/usr/bin/env python3
"""Read-only public DNS inspection. DNS answers do not prove ownership."""
import argparse
import datetime
import json
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("--host", default="voicegen.atbd.space")
parser.add_argument("--zone", default="atbd.space")
args = parser.parse_args()
records = []
for name, kind in [(args.zone, "NS"), (args.host, "A"), (args.host, "AAAA"), (args.host, "TXT"), (args.zone, "TXT")]:
    result = subprocess.run(["dig", "+time=3", "+tries=1", "+noall", "+comments", "+answer", name, kind], capture_output=True, text=True, check=False)
    records.append(dict(name=name, type=kind, exit_code=result.returncode, answer=result.stdout.strip(), error=result.stderr.strip()))
print(json.dumps(dict(observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), ownership="unknown; authoritative DNS or registrar access must be demonstrated separately", records=records), indent=2))
raise SystemExit(any(record["exit_code"] for record in records))
