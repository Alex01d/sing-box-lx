#!/usr/bin/env python3
"""Focused offline checks; integration cases read a separate pinned checkout."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import reference_overlay as overlay

REFERENCE_CHECKOUT = None


class ReferenceOverlayTest(unittest.TestCase):
    def setUp(self):
        self.reference = json.loads((overlay.HERE / 'dependencies.json').read_text())['reference']
        self.pin = self.reference['patch']
        self.patch = overlay.artifact(self.pin['file'])

    def checkout(self):
        if REFERENCE_CHECKOUT is None:
            self.skipTest('Pass --checkout for the pinned-source integration cases')
        return REFERENCE_CHECKOUT

    def test_reference_artifacts_have_separate_verified_pins(self):
        dependencies = json.loads((overlay.HERE / 'dependencies.json').read_text())
        self.assertEqual(overlay.sha256(self.patch), self.pin['sha256'])
        self.assertEqual(overlay.sha256(overlay.artifact(self.pin['regression_file'])), self.pin['regression_sha256'])
        self.assertNotIn(self.pin['file'], dependencies['patches'])
        self.assertNotIn(self.pin['file'], dependencies['patch_files'])

    def test_wrong_base_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'base file'):
            overlay.checked_source(b'wrong reference source\n', self.patch, self.pin)

    def test_wrong_patch_hash_is_rejected(self):
        pin = {**self.pin, 'base_sha256': overlay.sha256(b'fixture')}
        with self.assertRaisesRegex(ValueError, 'patch.*SHA256'):
            overlay.checked_source(b'fixture', self.patch + b'\n', pin)

    def test_output_inside_core_is_rejected_before_writing(self):
        with self.assertRaisesRegex(ValueError, 'outside both'):
            overlay.prepare_reference_overlay(Path('/unused-reference'), overlay.CORE / 'forbidden-overlay-output')

    def test_existing_output_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as work:
            with self.assertRaisesRegex(ValueError, 'new directory'):
                overlay.prepare_reference_overlay(Path('/unused-reference'), Path(work))

    def test_pinned_patch_produces_exact_proven_source_bytes(self):
        checkout = self.checkout()
        before = subprocess.check_output(['git', 'status', '--porcelain'], cwd=checkout)
        with tempfile.TemporaryDirectory() as work:
            output = Path(work) / 'overlay'
            metadata = overlay.prepare_reference_overlay(checkout, output)
            self.assertEqual(overlay.sha256((output / 'derp.go').read_bytes()),
                             '93721928aa26fd7bf1b4eae75422f17aff2d634d6a49e73e2865e3e58a5bf271')
            self.assertEqual(metadata['mode'], 'borrowed-read-ack-backport')
            self.assertTrue(metadata['patch_applied'])
            production = json.loads(Path(metadata['go_overlay']).read_text())
            self.assertEqual(production['Replace'], {str(checkout / overlay.TARGET): str(output / 'derp.go')})
            tests = json.loads(Path(metadata['test_overlay']).read_text())
            self.assertEqual(set(tests['Replace']), {str(checkout / overlay.TARGET), str(checkout / overlay.TEST_TARGET)})
        self.assertEqual(subprocess.check_output(['git', 'status', '--porcelain'], cwd=checkout), before)

    def test_wrong_patched_hash_is_rejected(self):
        base = (self.checkout() / overlay.TARGET).read_bytes()
        with self.assertRaisesRegex(ValueError, 'Patched reference.*SHA256'):
            overlay.checked_source(base, self.patch, {**self.pin, 'patched_sha256': '0' * 64})

    def test_wrong_reference_revision_is_rejected(self):
        reference = copy.deepcopy(self.reference)
        reference['revision'] = '0' * 40
        with self.assertRaisesRegex(ValueError, 'HEAD'):
            overlay.validate_reference(self.checkout(), reference)

    def test_stock_control_is_explicit_and_never_applies_production_overlay(self):
        checkout = self.checkout()
        with tempfile.TemporaryDirectory() as work:
            output = Path(work) / 'stock'
            metadata = overlay.prepare_reference_overlay(checkout, output, stock=True)
            self.assertEqual(metadata['mode'], 'stock-control')
            self.assertFalse(metadata['patch_applied'])
            self.assertIsNone(metadata['go_overlay'])
            self.assertFalse((output / 'derp.go').exists())
            test_overlay = json.loads(Path(metadata['test_overlay']).read_text())
            self.assertEqual(set(test_overlay['Replace']), {str(checkout / overlay.TEST_TARGET)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, required=True)
    args, remaining = parser.parse_known_args()
    REFERENCE_CHECKOUT = args.checkout.resolve()
    unittest.main(argv=[__file__, *remaining])
