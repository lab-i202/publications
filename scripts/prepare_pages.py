"""Prepare a public GitHub Pages artifact from a verified encrypted export.

Only static UI files and authenticated ciphertext are ever copied to dist/.
The optional refresh backend origin is public configuration (never credentials).
"""
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

ALLOWED = (
    'index.html', 'app.js', 'styles.css', '.nojekyll',
    'manifest.json', 'bundle.enc.json',
)
CSP_MARKER = "connect-src 'self';"


def validated_origin(value):
    value = value.strip()
    if not value:
        return ''
    if len(value) > 512:
        raise ValueError('PUBGROUP_REFRESH_API_URL is too long')
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or
            parsed.password or parsed.path not in ('', '/') or parsed.query or
            parsed.fragment or parsed.port not in (None, 443)):
        raise ValueError('PUBGROUP_REFRESH_API_URL must be an HTTPS origin with no path/query')
    return f'https://{parsed.netloc.rstrip("/")}'


def prepare(web, dist, refresh_url=''):
    web, dist = Path(web), Path(dist)
    origin = validated_origin(refresh_url)
    manifest = json.loads((web / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('encrypted') is not True or manifest.get('bundle') != 'bundle.enc.json':
        raise ValueError('Refusing to deploy an unencrypted publication catalogue')
    if not re.fullmatch('[0-9a-f]{64}', manifest.get('revision', '')):
        raise ValueError('Encrypted manifest revision is missing or invalid')
    ciphertext = json.loads((web / 'bundle.enc.json').read_text(encoding='utf-8'))
    if (ciphertext.get('encrypted') is not True or
            ciphertext.get('format') != 'PublicationGroup:v1' or
            ciphertext.get('algorithm') != 'AES-256-GCM' or
            ciphertext.get('kdf') != 'PBKDF2-SHA256' or
            ciphertext.get('iterations') != 600000 or
            not isinstance(ciphertext.get('ciphertext'), str)):
        raise ValueError('The expected encrypted publication bundle was not found')
    actual_revision = hashlib.sha256(ciphertext['ciphertext'].encode('ascii')).hexdigest()
    if actual_revision != manifest['revision']:
        raise ValueError('Manifest revision does not match encrypted bundle')
    if dist.exists() and (not dist.is_dir() or dist.is_symlink() or any(dist.iterdir())):
        raise ValueError('Deployment destination must be an empty directory')
    dist.mkdir(parents=True, exist_ok=True)
    for name in ALLOWED:
        if not (web / name).is_file():
            raise FileNotFoundError(f'Required deployment file missing: {name}')
        shutil.copyfile(web / name, dist / name)
    html = (dist / 'index.html').read_text(encoding='utf-8')
    if origin:
        if CSP_MARKER not in html:
            raise ValueError('Website CSP connect-src marker missing')
        html = html.replace(CSP_MARKER, f"connect-src 'self' {origin};", 1)
        (dist / 'index.html').write_text(html, encoding='utf-8')
    (dist / 'refresh-config.json').write_text(json.dumps({'api_base': origin}) + '\n', encoding='utf-8')
    return sorted(p.name for p in dist.iterdir())


if __name__ == '__main__':
    try:
        output = prepare('web', 'dist', os.environ.get('REFRESH_API_URL', ''))
    except (OSError, ValueError, UnicodeError) as exc:
        raise SystemExit(f'Pages deployment refused: {exc}') from exc
    print('Pages artifact allowlist:', ', '.join(output))
