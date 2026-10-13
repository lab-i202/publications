"""Security checks for encrypted state persisted in a public Actions cache."""
import json
import tempfile
import unittest
from pathlib import Path
from pubgroup.ci_state import save, restore, CONTEXT
from pubgroup.export import encrypt_payload

PHRASE = 'test-only random long collection phrase'

class EncryptedStateTests(unittest.TestCase):
    def setUp(self):
        try:
            import cryptography
        except ImportError:
            self.skipTest('optional cryptography not installed')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        (self.source / 'data').mkdir(parents=True)
        (self.source / 'cache' / 'http').mkdir(parents=True)
        (self.source / 'data' / 'state.json').write_text('{"title":"Private scientific result"}')
        self.body = self.source / 'cache' / 'http' / ('a' * 64 + '.body')
        self.body.write_bytes(b'<html>private-contact@example.com</html>')
        self.archive = self.root / 'state.enc.json'
        self.destination = self.root / 'restored'

    def test_roundtrip_excludes_plaintext_and_ignores_unrelated_files(self):
        (self.source / 'data' / 'collector.lock').touch()
        save(self.source, self.archive, PHRASE)
        text = self.archive.read_text()
        for value in ('Private scientific result', 'private-contact@example.com', 'state.json', PHRASE):
            self.assertNotIn(value, text)
        self.assertTrue(restore(self.destination, self.archive, PHRASE))
        self.assertEqual((self.destination / 'data' / 'state.json').read_bytes(),
                         (self.source / 'data' / 'state.json').read_bytes())
        self.assertEqual((self.destination / 'cache' / 'http' / self.body.name).read_bytes(), self.body.read_bytes())
        self.assertFalse((self.destination / 'data' / 'collector.lock').exists())

    def test_wrong_key_and_modified_ciphertext_write_nothing(self):
        from cryptography.exceptions import InvalidTag
        save(self.source, self.archive, PHRASE)
        with self.assertRaises(InvalidTag):
            restore(self.destination, self.archive, 'a different and long test phrase')
        self.assertFalse(self.destination.exists())
        envelope = json.loads(self.archive.read_text())
        envelope['ciphertext'] = ('A' if envelope['ciphertext'][0] != 'A' else 'B') + envelope['ciphertext'][1:]
        self.archive.write_text(json.dumps(envelope))
        with self.assertRaises(InvalidTag):
            restore(self.destination, self.archive, PHRASE)
        self.assertFalse(self.destination.exists())

    def test_rejects_traversal_before_writing_valid_files(self):
        envelope = encrypt_payload({'files': {'data/state.json': 'e30=', '../escape': 'e30='}},
                                   PHRASE, context=CONTEXT)
        self.archive.write_text(json.dumps(envelope))
        with self.assertRaises(ValueError):
            restore(self.destination, self.archive, PHRASE)
        self.assertFalse(self.destination.exists())

    def test_rejects_symlink_and_web_bundle_context(self):
        self.destination.mkdir()
        (self.destination / 'data').symlink_to(self.source / 'data', target_is_directory=True)
        save(self.source, self.archive, PHRASE)
        with self.assertRaises(ValueError):
            restore(self.destination, self.archive, PHRASE)
        self.archive.write_text(json.dumps(encrypt_payload({'files': {}}, PHRASE)))
        with self.assertRaises(ValueError):
            restore(self.root / 'other', self.archive, PHRASE)

    def test_missing_cache_establishes_new_baseline(self):
        self.assertFalse(restore(self.destination, self.archive, PHRASE))

if __name__ == '__main__':
    unittest.main()
