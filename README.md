# Publication Group

**Version 1.1.1 · build 20261013.3 · 13 October 2026**

Run this tool to collect the publications listed on eleven configured CiênciaVitae profiles, combine shared records, and produce a scientific production report in LaTeX, a BibTeX bibliography and a searchable webpage. The default report covers the current year in Europe/Lisbon. The web library includes the full catalogue and initially selects the report's year.

The interface uses the colours, rounded panels, system fonts and light/dark palette in the supplied `pdf_to_pptx` reference. That folder is untouched.

## Start

Requirements: Python 3.11 or later, `curl`, and XeLaTeX with `fontspec`, TeX Gyre Heros, `geometry`, `xcolor`, `hyperref`, `fancyhdr`, `tabularx`, `booktabs`, `needspace` and `tikz`. MacTeX or TeX Live includes these; BasicTeX may need additional packages. Network requests verify HTTPS certificates.

```sh
cd /path/to/publications_i202
python3 -m pubgroup run
python3 -m pubgroup serve
```

Open <http://127.0.0.1:8765>. The server binds to loopback only. Stop it with Ctrl+C.

The core collector has **no Python package dependencies**. Optional encrypted export needs:

```sh
python3 -m pip install -r requirements.txt
python3 -m pubgroup report --encrypt
```

This prompts for a passphrase. `PUBGROUP_PASSPHRASE` is supported for CI, but should be provided as a secret, never committed or typed into a command that stores it in history.

## Commands

```sh
python3 -m pubgroup --version
python3 -m pubgroup run                         # Collect using 24-hour HTTP cache
python3 -m pubgroup run --refresh               # Fetch sources again
python3 -m pubgroup run --period 2025           # Collect and report a specific year
python3 -m pubgroup run --period all            # Collect and report all years
python3 -m pubgroup run --offline               # Reuse cached source HTML and API responses
python3 -m pubgroup report --period current     # Build from saved state, no network
python3 -m pubgroup report --period all         # Build all years from saved state
python3 -m pubgroup run --no-enrich             # Skip DOI lookups
python3 -m pubgroup run --no-pdf                # Write LaTeX, JSON, BibTeX and web; no compiler
python3 -m pubgroup serve --port 8765
```

A run collects all years before filtering the report, so older records added recently are detected. The first run establishes a baseline and labels zero records as new. Later runs compare against `data/state.json`. Rebuilding a report does not fetch sources or change the baseline.

## Outputs

| Path | Purpose |
| --- | --- |
| `output/pdf/publications.pdf` | Current selected report |
| `output/pdf/publications.tex` | Complete editable LaTeX source |
| `output/publications.json` | Selected report plus full web catalogue and source evidence |
| `output/publications.bib` | Bibliography for the report period |
| `output/audit/` | Source status, DOI checks, suggestions, unreadable citations and changes |
| `data/state.json` | Saved catalogue and first-seen dates |
| `data/previous-state.json` | Previous collection for reviewing removed entries |
| `cache/http/` | Raw responses and fetch timestamps; contains full public CV HTML |
| `web/` | Only folder intended for website deployment |

Generated files are ignored by Git. Local outputs and caches are **not encrypted** by `--encrypt`; it encrypts the web export only. Raw public CVs can contain contact information, so deploy only the generated `web/` allowlist. A report build replaces the current report files. Copy a report elsewhere to retain multiple versions.

## Features

- Publication records from all eleven supplied profiles, including book/report titles written in italics instead of quotation marks.
- Shared records combined conservatively; distinct papers, chapters, posters, abstracts, theses, preprints, books and reports retained.
- Descending dates, with unknown months ordered last within their year.
- Current year, explicit year, all years or year range; type/status filters in configuration.
- Exact DOI checks in Crossref and DataCite; optional title searches produce review suggestions only.
- Cross-check of the public Zotero library linked by UPWIND; unmatched entries are listed for review.
- New and updated records tracked across collections; failed sources retain their previous entries.
- Scientific production report with output totals, a sourced monthly activity chart, conference participation, bibliography and an alphabetical linked researcher roster.
- Generic conference-date resolution using Crossref, linked webpages and optional Brave web search; source-backed results are cached.
- Web search, year/type/researcher/status/new filters, alphabetical researcher names, pagination, BibTeX and PDF downloads, and Light/Dark/System theme selection.
- Sources & changes presents a simple list of referenced webpages; detailed collection diagnostics stay in local audit files.
- Local webpage buttons for collection refresh and building a report for the selected year. These controls use the loopback collector. A static hosted webpage shows the command to run instead.
- Optional AES-256-GCM encrypted static export containing both the library and PDF.
- GitHub Pages workflow with manual collection/deployment, encrypted export enabled by default and encrypted persistent collection-state cache.

The monthly chart uses a sourced conference month for year-only conference contributions, and leaves other unresolved months unknown. A conference record count includes papers, posters and abstracts; a conference venue count groups sourced editions where available; it does not infer individual attendance. No researcher rankings or publication comparisons are shown.

## Documentation

- [Conference date discovery](docs/CONFERENCE_DATES.md)
- [Configuration](docs/CONFIGURATION.md)
- [Feature tutorials](docs/TUTORIALS.md)
- [Sources, matching and coverage](docs/SOURCES.md)
- [GitHub Pages and encryption](docs/DEPLOYMENT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Verification results](docs/VALIDATION.md)
- [Changelog](CHANGELOG.md)

## Tests

```sh
python3 -m unittest discover -s tests -v
```

Encryption tests skip when `cryptography` is absent. Install the optional dependency to run them. The tests also cover previously unseen conference discovery, explicit CV participation, deadline/edition rejection and sourced event-month fallback. The original tests cover date parsing, wrong/container DOIs, chronology, duplicate records, baseline changes, DOI upgrades, title conflicts, thesis BibTeX, encryption tampering and removal of plaintext web exports.

## Limits

The catalogue reflects publicly visible CV records, not a complete database of the group's research. It does not infer group membership at publication time. The supplied UPWIND team page is context, not another personal CV. Public HTML layouts can change. Missing dates, statuses, links and conflicts remain visible. No Google Scholar or Scopus scraping, private CV access, paywall bypass or unattended account login is included.

GitHub Pages cannot run the collector or LaTeX from a visitor's browser. Use the local collector or the supplied manual GitHub Actions workflow. An encrypted static export protects the content at rest with a sufficiently strong passphrase; it is not individual-user authentication or a WebAuthn passkey service.
