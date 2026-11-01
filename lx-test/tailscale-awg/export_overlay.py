#!/usr/bin/env python3
"""Maintainer helper: export only the reviewed dependency seams, never stage files."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

FILES = {
    'awg-device.patch': [
        'tsnet/tsnet.go', 'wgengine/userspace.go', 'wgengine/magicsock/magicsock.go',
        'wgengine/magicsock/derp.go', 'derp/derphttp/derphttp_client.go', 'control/controlhttp/client.go',
        'derp/derphttp/underlay_lx.go', 'wgengine/wireguard_device_lx.go',
        'wgengine/wireguard_classifier_lx.go', 'wgengine/magicsock/wireguard_classifier_lx.go',
        'wgengine/magicsock/awg_framing_lx_test.go',
        'wgengine/magicsock/force_derp_rebind_lx_test.go',
    ],
    'security-serve.patch': [
        'ipn/ipnlocal/serve.go', 'ipn/ipnlocal/serve_security_lx.go',
        'ipn/ipnlocal/serve_unix_linux.go', 'ipn/ipnlocal/serve_unix_other.go',
        'ipn/ipnlocal/serve_security_lx_test.go',
    ],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--checkout', type=Path, required=True)
    args = ap.parse_args()
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / 'dependencies.json').read_text())
    checkout = args.checkout.resolve()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip()
    if head != manifest['tailscale']['revision']:
        raise SystemExit('Checkout does not match the reviewed baseline')
    for name, files in FILES.items():
        patch = ''
        for path in files:
            tracked = subprocess.run(['git', 'cat-file', '-e', 'HEAD:' + path], cwd=checkout, stderr=subprocess.DEVNULL).returncode == 0
            if tracked:
                patch += subprocess.check_output(['git', 'diff', 'HEAD', '--', path], cwd=checkout, text=True)
            else:
                patch += 'diff --git a/' + path + ' b/' + path + '\nnew file mode 100644\n'
                patch += ''.join(difflib.unified_diff([], (checkout / path).read_text().splitlines(True), fromfile='/dev/null', tofile='b/' + path))
        (here / name).write_text(patch)
    manifest['patches'] = {name: hashlib.sha256((here / name).read_bytes()).hexdigest() for name in FILES}
    manifest['patch_files'] = FILES
    (here / 'dependencies.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
