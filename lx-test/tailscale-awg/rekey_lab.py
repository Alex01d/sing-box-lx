#!/usr/bin/env python3
"""Prove live rekey with an unchanged per-device profile, using real peer traffic."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import time

from lab import request, wait_for, write


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    args = ap.parse_args()
    cases = []
    for mode, offset in [('plain', 10), ('awg2', 20), ('awg3', 30)]:
        sender = f'10.253.143.{offset + 1}'
        peer = request(f'http://10.253.143.{offset}:9080/status')['TailscaleIPs'][0]
        result = wait_for(lambda: request(f'http://{sender}:9080/probe?peer={peer}'))
        cases.append((mode, sender, peer, result['last_handshake']))
    # WireGuard's default rekey-after-time is 120s. No device or state restart.
    print('Initial traffic passed; waiting 130s for the live-key rotation gate.', flush=True)
    deadline = time.monotonic() + 130
    while time.monotonic() < deadline:
        time.sleep(min(5, deadline - time.monotonic()))
    results = []
    for mode, sender, peer, previous in cases:
        def rotated():
            current = request(f'http://{sender}:9080/probe?peer={peer}')
            before = datetime.fromisoformat(previous.replace('Z', '+00:00'))
            after = datetime.fromisoformat(current['last_handshake'].replace('Z', '+00:00'))
            if after <= before:
                raise RuntimeError('waiting for a newer authenticated handshake')
            return current
        result = wait_for(rotated, seconds=40)
        results.append({'mode': mode, 'passed': True, 'previous_handshake': previous,
                        'new_handshake': result['last_handshake'],
                        'tcp_bytes_each_direction': result['tcp_bytes_each_direction'],
                        'udp_payloads': result['udp_payloads'], 'sha256': result['sha256']})
    write(args.root / 'rekey-results.json', results)
    print(json.dumps(results, indent=2), flush=True)


if __name__ == '__main__':
    main()
