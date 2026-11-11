"""A multi-runtime font binding is not server code merely because its guarded Node implementation uses argv."""
import unittest
from needs import needs
from eaos.features.layers.analysis.placement import _written
from eaos.features.code_reading.facts.code.syntax import parser_for

RUNTIME = '''
let ENVIRONMENT_IS_WEB = false;
let ENVIRONMENT_IS_WORKER = false;
let ENVIRONMENT_HAS_NODE = false;
let ENVIRONMENT_IS_NODE = false;
ENVIRONMENT_IS_WEB = typeof window === "object";
ENVIRONMENT_IS_WORKER = typeof importScripts === "function";
ENVIRONMENT_HAS_NODE = typeof process === "object" && typeof process.versions === "object" && typeof process.versions.node === "string";
ENVIRONMENT_IS_NODE = ENVIRONMENT_HAS_NODE && !ENVIRONMENT_IS_WEB && !ENVIRONMENT_IS_WORKER;
if (ENVIRONMENT_IS_NODE) { const args = process.argv; const root = __dirname; }
else { document.currentScript; }
'''


@needs('' if parser_for('typescript') else 'TypeScript parser unavailable')
class RuntimeGuardTests(unittest.TestCase):
    def test_only_the_proven_node_branch_is_excluded_from_text_evidence(self):
        self.assertEqual(_written('binding.ts', RUNTIME), {'browser'})
        for text in (RUNTIME + '\nprocess.argv;',
                     RUNTIME.replace('!ENVIRONMENT_IS_WEB', 'ENVIRONMENT_IS_WEB'),
                     RUNTIME.replace('if (ENVIRONMENT_IS_NODE)', 'ENVIRONMENT_IS_NODE = true; if '
                                     '(ENVIRONMENT_IS_NODE)'),
                     RUNTIME.replace('else { document.currentScript; }', 'else { document.currentScript; process.argv; '
                                     '}'),
                     RUNTIME.replace('if (ENVIRONMENT_IS_NODE)', 'if (!ENVIRONMENT_IS_NODE)')):
            with self.subTest(text=text): self.assertIn('node', _written('binding.ts', text))
