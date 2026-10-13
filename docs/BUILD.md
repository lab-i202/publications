# Build and release

Version 1.1.1 · build 20261013.3

The delivered source is complete. No hidden collection/report backend is required. Python uses the standard library, HTTPS requests use system `curl`, LaTeX compilation uses local XeLaTeX, and browser encryption uses Web Crypto. `cryptography` is optional locally and used for encrypted exports and encrypted Actions state. The Pages workflow installs it.

## Build locally

```sh
python3 -m unittest discover -s tests -v
python3 -m pubgroup run
python3 -m pubgroup serve
```

Install a full TeX distribution or the packages listed in the README. The report loads TeX Gyre Heros by its OpenType filenames so it works without installing the font family into the operating system. Compilation runs twice with shell escape disabled. `--no-pdf` writes LaTeX and removes the stale report PDF, while disabling the web PDF download.

The project can also be installed using `python3 -m pip install -e .`; the equivalent CLI is `pubgroup`. Retain the configuration and web assets in the project folder.

## Create a release archive

```sh
python3 scripts/package_release.py
python3 scripts/package_release.py --include-snapshot
```

The first command packages only source, configuration, documentation, tests, workflow and web assets. The second also packages the normalized public-data snapshot, collection state, sample reports and ready-to-serve website. The archive is written to `output/release/`, with a SHA-256 checksum file. SHA-256 here verifies archive integrity; it is not encryption.

Archives have distinct `-source-only.zip` and `-snapshot.zip` filenames. Use **source-only** when creating a public repository. It contains no collected data, state, PDF, BibTeX, raw HTML or passphrase. The configuration contains public profile identifiers and the group name; these become public with the code.

A snapshot archive is for local inspection and offline report rebuilding. It can contain plaintext normalized records and sample PDF reports, even if the website export was encrypted. Do not upload that archive to a public GitHub release or use browser upload to publish its contents. Neither archive includes raw CV HTML, credentials, compiler logs, temporary screenshots or the reference project's Git repository. Git ignores generated snapshot files after extraction, but browser uploads and release attachments do not apply `.gitignore`.

The current report and the separately archived all-years report both include matching editable LaTeX sources. Future report commands replace `publications.pdf`/`.tex`; copy outputs before creating another edition if you need both.

## Update version/build

Update `pubgroup/__init__.py`, `pyproject.toml`, the fallback web version text, configuration header and documentation when releasing a new version. Generated data and reports read their version/build from the Python package. Add a changelog entry and rerun verification before packaging.
