#!/usr/bin/env python3
"""Validate config boundaries through the public CLI. Never starts a VPN."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', type=Path, required=True)
    ap.add_argument('--without-integration', type=Path, required=True)
    args = ap.parse_args()
    secret = 'synthetic-secret-must-not-appear-in-errors'
    base = {'type': 'tailscale', 'tag': 'test', 'control_url': 'https://127.0.0.1:9',
            'awg': {'version': 2, 'profile_id': 'synthetic', 'parameters': {'s1': 16}}}
    cases = [('valid-awg2', base, True)]
    for name, patch in [
        ('private-key', {'parameters': {'private_key': secret}}),
        ('header-key', {'version': 3, 'parameters': {'header_protection_key': secret}}),
        ('cps-injection', {'parameters': {'i1': '<r 10>\nprivate_key=' + secret}}),
        ('invalid-version', {'version': 1}),
        ('empty', {'parameters': {}}),
        ('classic-range', {'parameters': {'h1': '1-1', 'h2': '2-2', 'h3': '3-3', 'h4': '4-4'}}),
        ('unknown-wrapper', {'future': secret}),
    ]:
        endpoint = copy.deepcopy(base)
        endpoint['awg'].update(patch)
        cases.append((name, endpoint, False))
    for name, field, value in [('invalid-carrier', 'underlay_mode', 'invalid'),
                               ('peer-relay', 'relay_server_port', 17123),
                               ('ssh-server', 'ssh_server', True)]:
        endpoint = copy.deepcopy(base)
        endpoint[field] = value
        cases.append((name, endpoint, False))
    with tempfile.TemporaryDirectory(prefix='lx-awg143-check-') as directory:
        directory = Path(directory)
        results = []
        for name, endpoint, accepted in cases:
            endpoint = copy.deepcopy(endpoint)
            endpoint['state_directory'] = str(directory / name)
            config = directory / 'config.json'
            config.write_text(json.dumps({'endpoints': [endpoint]}))
            result = subprocess.run([str(args.candidate.resolve()), 'check', '-c', str(config)], capture_output=True, text=True)
            assert (result.returncode == 0) == accepted, name + ': unexpected validation result'
            assert secret not in result.stdout + result.stderr, name + ': secret appeared in diagnostic'
            results.append({'case': name, 'passed': True, 'accepted': accepted})
        for name, endpoint in [('awg', base), ('carrier', {'type': 'tailscale', 'tag': 'test', 'underlay_mode': 'derp'})]:
            config.write_text(json.dumps({'endpoints': [endpoint]}))
            result = subprocess.run([str(args.without_integration.resolve()), 'check', '-c', str(config)], capture_output=True, text=True)
            assert result.returncode != 0 and 'tailscale_awg_core_unsupported' in result.stderr, name + ': integration silently downgraded'
            results.append({'case': 'missing-capability-' + name, 'passed': True, 'accepted': False})
        config.write_text(json.dumps({'endpoints': [{'type': 'tailscale', 'tag': 'plain'}]}))
        result = subprocess.run([str(args.without_integration.resolve()), 'check', '-c', str(config)], capture_output=True, text=True)
        assert result.returncode == 0, 'ordinary Tailscale regressed'
        results.append({'case': 'plain-without-integration', 'passed': True, 'accepted': True})
        print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
