"""Encrypt persistent Actions state; never cache plaintext CVs or catalogue files."""
import argparse
import base64
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from .export import encrypt_payload, decrypt_payload
from .state import atomic_json

CONTEXT = b'PublicationGroupCI:v1'
STATE_FILES = ('state.json', 'previous-state.json', 'conference_dates.json')

def target(root, name):
    parts = PurePosixPath(name).parts
    allowed = (len(parts) == 2 and parts[0] == 'data' and parts[1] in STATE_FILES)
    allowed |= (len(parts) == 3 and parts[:2] == ('cache', 'http') and
                bool(re.fullmatch(r'[0-9a-f]{64}\.(?:body|json)', parts[2])))
    if not allowed or PurePosixPath(name).as_posix() != name:
        raise ValueError('Encrypted state contains a disallowed path')
    result = root.joinpath(*parts)
    if any(p.is_symlink() for p in (result, *result.parents) if p != root.parent):
        raise ValueError('Encrypted state paths must not be symbolic links')
    return result

def save(root, archive, passphrase):
    root = Path(root).resolve()
    if not (root / 'data' / 'state.json').is_file():
        raise ValueError('No collection baseline to save')
    paths = [root / 'data' / n for n in STATE_FILES]
    paths += sorted((root / 'cache' / 'http').glob('*'))
    files = {}
    for path in paths:
        if path.is_file():
            name = path.relative_to(root).as_posix()
            target(root, name)
            files[name] = base64.b64encode(path.read_bytes()).decode('ascii')
    atomic_json(archive, encrypt_payload({'files': files}, passphrase, context=CONTEXT))

def restore(root, archive, passphrase):
    archive = Path(archive)
    if not archive.is_file():
        return False
    root = Path(root).resolve()
    payload = decrypt_payload(json.loads(archive.read_text()), passphrase, context=CONTEXT)
    files = payload['files']
    if not isinstance(files, dict) or 'data/state.json' not in files:
        raise ValueError('Encrypted state has no collection baseline')
    # Validate every path and value before writing any file. No general archive extraction.
    writes = [(target(root, name), base64.b64decode(value, validate=True)) for name, value in files.items()]
    for path, value in writes:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            handle.write(value)
            temporary = Path(handle.name)
        os.replace(temporary, path)
    return True

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('save', 'restore'))
    parser.add_argument('--archive', default='.ci-private/state.enc.json')
    args = parser.parse_args()
    passphrase = os.environ.get('PUBGROUP_PASSPHRASE', '')
    if len(passphrase) < 16:
        parser.exit(1, 'Configure PUBGROUP_PASSPHRASE with at least 16 characters.\n')
    try:
        result = globals()[args.operation](Path.cwd(), Path(args.archive), passphrase)
    except Exception:
        # Avoid printing source payloads, keys, or crypto exception internals to public logs.
        parser.exit(1, 'Cannot authenticate or write encrypted collection state. Check the passphrase; use reset_state when deliberately changing it.\n')
    print('No cached baseline; this run starts a new baseline.' if result is False else
          'Encrypted collection state ' + ('restored.' if args.operation == 'restore' else 'saved.'))

if __name__ == '__main__':
    main()
