"""CI deployment cannot accidentally publish plaintext collections."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_pages import prepare, validated_origin
from pubgroup.export import build_web

ROOT = Path(__file__).resolve().parents[1]


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        try:
            import cryptography
        except ImportError:
            self.skipTest('Encrypted export requires optional cryptography')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.web, self.dist = root / 'web', root / 'dist'
        self.web.mkdir()
        for name in ('index.html', 'styles.css', 'app.js', '.nojekyll'):
            (self.web / name).write_bytes((ROOT / 'web' / name).read_bytes())
        build_web({'publications': []}, None, self.web, 'a sufficiently long test passphrase')
        # Simulate old, accidentally generated plaintext files alongside ciphertext.
        (self.web / 'publications.json').write_text('PRIVATE RECORDS')
        (self.web / 'report.pdf').write_text('PRIVATE PDF')

    def test_encrypted_allowlist_and_csp(self):
        names = prepare(self.web, self.dist, 'https://pubgroup-refresh.example.workers.dev')
        self.assertEqual(len(names), 7)
        self.assertNotIn('publications.json', names)
        self.assertNotIn('report.pdf', names)
        self.assertNotIn('publications.bib', names)
        self.assertIn("connect-src 'self' https://pubgroup-refresh.example.workers.dev;",
                      (self.dist / 'index.html').read_text())
        self.assertEqual(json.loads((self.dist / 'refresh-config.json').read_text()),
                         {'api_base': 'https://pubgroup-refresh.example.workers.dev'})

    def test_unencrypted_or_tampered_bundle_is_refused(self):
        manifest_file = self.web / 'manifest.json'
        manifest = json.loads(manifest_file.read_text())
        manifest['encrypted'] = False
        manifest_file.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'unencrypted'):
            prepare(self.web, self.dist)
        manifest['encrypted'] = True
        manifest_file.write_text(json.dumps(manifest))
        bundle_file = self.web / 'bundle.enc.json'
        bundle = json.loads(bundle_file.read_text())
        bundle['ciphertext'] += 'foo'
        bundle_file.write_text(json.dumps(bundle))
        with self.assertRaisesRegex(ValueError, 'revision'):
            prepare(self.web, self.dist)

    def test_worker_url_cannot_include_credentials_or_insecure_transport(self):
        for value in ('http://example.com', 'https://user:pass@example.com',
                      'https://example.com/refresh', 'https://example.com?token=123'):
            with self.assertRaises(ValueError):
                validated_origin(value)


if __name__ == '__main__':
    unittest.main()
