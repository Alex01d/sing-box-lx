#!/usr/bin/env python3
"""Build a hash-pinned reference overlay without editing its clean checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
CORE = HERE.parents[1]
TARGET = 'wgengine/magicsock/derp.go'
TEST_TARGET = 'wgengine/magicsock/derp_bind_close_ack_reference_overlay_test.go'


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def checked_source(base, patch, pin):
    """Accept only the pinned one-file/one-hunk patch and its exact output."""
    if pin['base_file'] != TARGET or sha256(base) != pin['base_sha256']:
        raise ValueError('Reference base file does not match its SHA256 pin')
    if sha256(patch) != pin['sha256']:
        raise ValueError('Reference patch does not match its SHA256 pin')
    lines = patch.decode().splitlines(keepends=True)
    if lines[:2] != [f'--- a/{TARGET}\n', f'+++ b/{TARGET}\n']:
        raise ValueError('Reference patch must touch only the reviewed file')
    hunk = re.fullmatch(r'@@ -(\d+),(\d+) \+(\d+),(\d+) @@\n', lines[2])
    if not hunk or any(line[:1] not in (' ', '+', '-') for line in lines[3:]):
        raise ValueError('Reference patch must contain one ordinary unified hunk')
    start, old_count, new_start, new_count = map(int, hunk.groups())
    old = [line[1:] for line in lines[3:] if line[0] in ' -']
    new = [line[1:] for line in lines[3:] if line[0] in ' +']
    original = base.decode().splitlines(keepends=True)
    if (start < 1 or new_start != start or len(old) != old_count
            or len(new) != new_count or original[start - 1:start - 1 + old_count] != old):
        raise ValueError('Reference patch context does not match the pinned base')
    result = ''.join(original[:start - 1] + new + original[start - 1 + old_count:]).encode()
    if sha256(result) != pin['patched_sha256']:
        raise ValueError('Patched reference file does not match its SHA256 pin')
    return result


def validate_reference(checkout, reference):
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip()
    if head != reference['revision']:
        raise ValueError('Reference HEAD does not match the reviewed revision')
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=checkout, text=True):
        raise ValueError('Reference checkout must be clean')
    path = checkout / TARGET
    if path.is_symlink() or sha256(path.read_bytes()) != reference['patch']['base_sha256']:
        raise ValueError('Reference base file does not match its SHA256 pin')
    return head


def artifact(name):
    path = HERE / name
    if Path(name).name != name or path.is_symlink():
        raise ValueError('Reference artifacts must be ordinary files beside this helper')
    return path.read_bytes()


def prepare_reference_overlay(checkout, output, *, stock=False):
    reference = json.loads((HERE / 'dependencies.json').read_text())['reference']
    checkout, output = Path(checkout).resolve(), Path(output).resolve()
    if output.is_relative_to(checkout) or output.is_relative_to(CORE):
        raise ValueError('Reference overlay output must be outside both source checkouts')
    if output.exists():
        raise ValueError('Reference overlay output must be a new directory')
    head = validate_reference(checkout, reference)
    pin = reference['patch']
    patched = checked_source((checkout / TARGET).read_bytes(), artifact(pin['file']), pin)
    test = artifact(pin['regression_file'])
    if sha256(test) != pin['regression_sha256']:
        raise ValueError('Reference regression does not match its SHA256 pin')
    output.mkdir(parents=True, mode=0o700)
    test_path = output / Path(TEST_TARGET).name
    test_path.write_bytes(test)
    replacements = {}
    if not stock:
        patched_path = output / 'derp.go'
        patched_path.write_bytes(patched)
        replacements[str(checkout / TARGET)] = str(patched_path)
        (output / 'go-overlay.json').write_text(json.dumps({'Replace': replacements}, indent=2) + '\n')
    test_replacements = {**replacements, str(checkout / TEST_TARGET): str(test_path)}
    (output / 'go-test-overlay.json').write_text(json.dumps({'Replace': test_replacements}, indent=2) + '\n')
    metadata = {
        'mode': 'stock-control' if stock else 'borrowed-read-ack-backport',
        'checkout': str(checkout),
        'revision': head,
        'checkout_clean': True,
        'go': reference['go'],
        'patch_applied': not stock,
        'patch_file': pin['file'],
        'patch_sha256': pin['sha256'],
        'base_file': TARGET,
        'base_sha256': pin['base_sha256'],
        'expected_patched_sha256': pin['patched_sha256'],
        'regression_sha256': pin['regression_sha256'],
        'go_overlay': None if stock else str(output / 'go-overlay.json'),
        'test_overlay': str(output / 'go-test-overlay.json'),
        'scope': pin['scope'],
        'removal_condition': pin['removal_condition'],
    }
    (output / 'reference-overlay.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='new external directory')
    parser.add_argument('--stock-reference', action='store_true', help='unpatched control; regression is expected RED')
    args = parser.parse_args()
    print(json.dumps(prepare_reference_overlay(args.checkout, args.output, stock=args.stock_reference), indent=2))


if __name__ == '__main__':
    main()
