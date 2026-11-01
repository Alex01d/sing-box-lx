#!/usr/bin/env python3
"""Prepare a pinned, external engineering workspace; never alter the core checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def run(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, required=True, help='new directory')
    parser.add_argument('--core', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--dependency-source', default='https://github.com/SagerNet/tailscale.git')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / 'dependencies.json').read_text())
    core = args.core.resolve()
    workspace = args.workspace.resolve()
    if workspace.exists():
        raise SystemExit('Workspace already exists; refusing to overwrite it')
    for name, revision in manifest['submodules'].items():
        if run('git', 'rev-parse', 'HEAD', cwd=core / 'submodules' / name) != revision:
            raise SystemExit('Initialize the documented submodule pin: ' + name)
    for name, digest in manifest['patches'].items():
        if hashlib.sha256((here / name).read_bytes()).hexdigest() != digest:
            raise SystemExit('Patch checksum mismatch: ' + name)
    workspace.mkdir(parents=True, mode=0o700)
    dependency = workspace / 'tailscale'
    run('git', 'clone', '--no-checkout', args.dependency_source, str(dependency))
    revision = manifest['tailscale']['revision']
    run('git', 'checkout', '--detach', revision, cwd=dependency)
    if run('git', 'rev-parse', 'HEAD', cwd=dependency) != revision:
        raise SystemExit('Unexpected dependency revision')
    for name in manifest['patches']:
        run('git', 'apply', '--check', str(here / name), cwd=dependency)
        run('git', 'apply', str(here / name), cwd=dependency)
    modules = {'wireguard-go': 'github.com/sagernet/wireguard-go',
               'sing-tun': 'github.com/sagernet/sing-tun',
               'gvisor': 'github.com/sagernet/gvisor',
               'utls': 'github.com/metacubex/utls'}
    quote = lambda p: json.dumps(str(p))
    text = 'go 1.26.10\n\nuse (\n\t' + quote(core) + '\n\t' + quote(dependency) + '\n)\n\n'
    for name, module in modules.items():
        text += 'replace ' + module + ' => ' + quote(core / 'submodules' / name) + '\n'
    (workspace / 'go.work').write_text(text)
    print('GOWORK=' + str(workspace / 'go.work'))
    print('Build: GOTOOLCHAIN=go1.26.10 CGO_ENABLED=0 make -f Makefile.lx lx-build LX_TAILSCALE_AWG=1 LX_OUTPUT=<new-binary>')


if __name__ == '__main__':
    main()
