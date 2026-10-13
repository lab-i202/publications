"""Create a release ZIP from an explicit source allowlist. No credentials/raw CVs."""
import argparse
import hashlib
import zipfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pubgroup import __version__, BUILD

parser = argparse.ArgumentParser()
parser.add_argument('--include-snapshot', action='store_true', help='Include normalized public data, state, website and sample reports')
args = parser.parse_args()
files = [ROOT / name for name in ('README.md', 'CHANGELOG.md', 'config.toml', 'pyproject.toml', 'requirements.txt', '.gitignore')]
for folder, pattern in [('pubgroup','*.py'),('tests','*.py'),('docs','*.md'),('scripts','*.py'),('.github/workflows','*.yml')]:
    files += sorted((ROOT / folder).glob(pattern))
files += [ROOT / 'web' / n for n in ('index.html','app.js','styles.css','.nojekyll')]
if args.include_snapshot:
    files += [ROOT / 'data' / 'state.json', ROOT / 'data' / 'conference_dates.json']
    files += [ROOT / 'web' / n for n in ('manifest.json','publications.json','publications.bib','report.pdf','bundle.enc.json') if (ROOT / 'web' / n).is_file()]
    files += [ROOT / 'output' / n for n in ('publications.json','publications.bib')]
    files += list((ROOT / 'output' / 'audit').glob('*.json'))
    files += [ROOT / 'output' / 'pdf' / n for n in ('publications.pdf','publications.tex','publications-all-years.pdf','publications-all-years.tex')]
out = ROOT / 'output' / 'release'; out.mkdir(parents=True, exist_ok=True)
kind = 'snapshot' if args.include_snapshot else 'source-only'
zip_path = out / f'publication-group-{__version__}-build-{BUILD}-{kind}.zip'
with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        if path.is_file():
            archive.write(path, str(Path('publication-group-' + __version__) / path.relative_to(ROOT)))
checksum = hashlib.sha256(zip_path.read_bytes()).hexdigest()
zip_path.with_suffix('.sha256').write_text(checksum + '  ' + zip_path.name + '\n')
print(zip_path)
print(f'{len(files)} allowlisted files; SHA-256 {checksum}')
