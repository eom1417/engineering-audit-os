"""NS36.T1 — the Studio's decisions and contract core exist before any line of the interface is written.

Written by the planner with the plan (2026-10-08, docs/north-star.json NS36), before the code; it fails today.

Interface this task must provide:
    docs/STUDIO.md                        the decision record: D1-D5 as approved by the owner (place, one model for
                                          REPORT.html and the Studio, start order, stack, product-plan order), the
                                          contract version, and the plan model
    schemas/artifacts/studio-manifest.schema.json
                                          x-artifact "studio/manifest.json"; "x-sections" lists every data section the
                                          Studio reads, each with its own schemas/artifacts/studio-<section>.schema.json
    eaos/data/schemas/artifacts/          the packaged copy of every studio-*.schema.json, byte for byte
    artifact_contracts.validate           resolves "$ref" to "#/$defs/..." and enforces minimum/maximum
    build_info.studio_digest()            a fingerprint of the Studio's built assets, separate from digest()
"""
import json
import unittest
from pathlib import Path

from eaos import artifact_contracts, build_info

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'schemas/artifacts'
PACKAGED = ROOT / 'eaos/data/schemas/artifacts'
SECTIONS = {'meta', 'head', 'health', 'cards', 'evidence', 'story', 'docs', 'plans', 'decisions', 'media'}


class DecisionRecord(unittest.TestCase):
    def test_the_record_names_the_five_approved_decisions_and_the_contract_version(self):
        text = (ROOT / 'docs/STUDIO.md').read_text(encoding='utf-8')
        for key in ('D1', 'D2', 'D3', 'D4', 'D5'):
            self.assertRegex(text, rf'(?m)^#+ .*\b{key}\b', f'{key} has no heading in docs/STUDIO.md')
        self.assertRegex(text, r'contract v\d+')


class Contract(unittest.TestCase):
    def manifest(self):
        return json.loads((SOURCE / 'studio-manifest.schema.json').read_text(encoding='utf-8'))

    def test_the_manifest_lists_every_section_and_each_has_its_schema(self):
        manifest = self.manifest()
        self.assertEqual(manifest['x-artifact'], 'studio/manifest.json')
        self.assertTrue(SECTIONS <= set(manifest['x-sections']), SECTIONS - set(manifest['x-sections']))
        for section in manifest['x-sections']:
            schema = json.loads((SOURCE / f'studio-{section}.schema.json').read_text(encoding='utf-8'))
            self.assertEqual(schema['x-artifact'], f'studio/{section}.json')

    def test_the_packaged_copy_matches_the_source_byte_for_byte(self):
        names = sorted(path.name for path in SOURCE.glob('studio-*.schema.json'))
        self.assertTrue(names)
        for name in names:
            self.assertEqual((PACKAGED / name).read_bytes(), (SOURCE / name).read_bytes(), name)


class Validator(unittest.TestCase):
    def test_refs_and_bounds_are_enforced(self):
        schema = {'$defs': {'ratio': {'type': 'number', 'minimum': 0, 'maximum': 1}},
                  'type': 'object', 'properties': {'value': {'$ref': '#/$defs/ratio'}}}
        self.assertEqual(artifact_contracts.validate({'value': 0.5}, schema), [])
        self.assertTrue(artifact_contracts.validate({'value': 1.5}, schema))
        self.assertTrue(artifact_contracts.validate({'value': -1}, schema))
        self.assertTrue(artifact_contracts.validate({'value': 'x'}, schema))


class Digest(unittest.TestCase):
    def test_the_studio_has_a_digest_of_its_own(self):
        value = build_info.studio_digest()
        self.assertRegex(value, r'^[0-9a-f]{16,64}$')
        self.assertNotEqual(value, build_info.digest())


if __name__ == '__main__':
    unittest.main()
