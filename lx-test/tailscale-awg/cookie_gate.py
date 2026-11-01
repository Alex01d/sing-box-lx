#!/usr/bin/env python3
"""Run a synthetic test overlay without editing a pinned submodule file."""
import json
from pathlib import Path
import subprocess
import tempfile

here = Path(__file__).resolve().parent
core = here.parents[1]
with tempfile.TemporaryDirectory(prefix='lx-awg143-cookie-') as temporary:
    overlay = Path(temporary) / 'overlay.json'
    overlay.write_text(json.dumps({'Replace': {
        str(core / 'submodules/wireguard-go/device/awg_cookie_gate_lx_test.go'):
        str(here / 'wireguard_cookie_test.go.txt'),
    }}))
    subprocess.run(['go', 'test', '-race', '-overlay', str(overlay),
                    'github.com/sagernet/wireguard-go/device', '-run',
                    '^(TestAWGCookieHeadroomGateLX|TestSendHeadroomWireGuard|TestSendHeadroomAWG2|TestSendHeadroomAWG3)$',
                    '-count=1'], cwd=core, check=True)
