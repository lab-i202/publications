"""Static web export; optional AES-256-GCM bundle protects data and PDF together."""
import base64
import hashlib
import json
import os
import shutil
from pathlib import Path
from .model import bibtex
from .state import atomic_json

AAD = b'PublicationGroup:v1'
ITERATIONS = 600_000

def encrypt_payload(payload, passphrase, *, context=AAD):
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise RuntimeError('Encrypted export needs: python -m pip install cryptography') from exc
    if len(passphrase) < 16:
        raise ValueError('Use a passphrase of at least 16 characters; a longer random phrase is recommended')
    salt, nonce = os.urandom(16), os.urandom(12)
    key = hashlib.pbkdf2_hmac('sha256', passphrase.encode('utf-8'), salt, ITERATIONS, dklen=32)
    ciphertext = AESGCM(key).encrypt(nonce, json.dumps(payload, ensure_ascii=False).encode('utf-8'), context)
    b64 = lambda b: base64.b64encode(b).decode('ascii')
    return dict(format=context.decode('ascii'), encrypted=True, algorithm='AES-256-GCM',
                kdf='PBKDF2-SHA256', iterations=ITERATIONS, salt=b64(salt), iv=b64(nonce),
                ciphertext=b64(ciphertext))

def decrypt_payload(envelope, passphrase, *, context=AAD):
    """Authenticate a supported envelope before returning its decoded contents."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if (envelope.get('format') != context.decode('ascii') or
            envelope.get('algorithm') != 'AES-256-GCM' or
            envelope.get('kdf') != 'PBKDF2-SHA256' or
            envelope.get('iterations') != ITERATIONS):
        raise ValueError('Unsupported encrypted envelope')
    salt = base64.b64decode(envelope['salt'], validate=True)
    nonce = base64.b64decode(envelope['iv'], validate=True)
    if len(salt) != 16 or len(nonce) != 12:
        raise ValueError('Invalid encrypted envelope salt or nonce')
    key = hashlib.pbkdf2_hmac('sha256', passphrase.encode('utf-8'), salt, ITERATIONS, dklen=32)
    plaintext = AESGCM(key).decrypt(nonce, base64.b64decode(envelope['ciphertext'], validate=True), context)
    return json.loads(plaintext)

def build_web(dataset, pdf, destination, passphrase=None):
    destination = Path(destination); destination.mkdir(parents=True, exist_ok=True)
    encrypted_bundle = None
    if passphrase:
        payload = dict(dataset=dataset, bibliography='\n'.join(p['bibtex'] for p in dataset['publications']),
                       pdf=base64.b64encode(Path(pdf).read_bytes()).decode('ascii') if pdf else None)
        encrypted_bundle = encrypt_payload(payload, passphrase)
    # Fixed allowlist, never a recursive wipe. Assets remain intact between modes.
    for name in ('publications.json', 'report.pdf', 'publications.bib', 'bundle.enc.json', 'manifest.json'):
        (destination / name).unlink(missing_ok=True)
    bibliography = '\n'.join(p['bibtex'] for p in dataset['publications'])
    if passphrase:
        atomic_json(destination / 'bundle.enc.json', encrypted_bundle)
        manifest = dict(encrypted=True, bundle='bundle.enc.json',
                        revision=hashlib.sha256(encrypted_bundle['ciphertext'].encode('ascii')).hexdigest())
    else:
        atomic_json(destination / 'publications.json', dataset)
        (destination / 'publications.bib').write_text(bibliography, encoding='utf-8')
        if pdf:
            shutil.copy2(pdf, destination / 'report.pdf')
        manifest = dict(encrypted=False, dataset='publications.json',
                        bibliography='publications.bib', pdf='report.pdf' if pdf else None)
    atomic_json(destination / 'manifest.json', manifest)
    (destination / '.nojekyll').touch()
