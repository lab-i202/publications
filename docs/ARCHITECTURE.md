# Architecture

Version 1.1.1 · build 20261013.3

```text
config.toml
   ↓
network.py → HTTPS curl, robots, retry, cache
   ↓
parser.py → isolated publication table + professional identity
   ↓
model.py → normalize, merge, chronology, metrics, BibTeX
   ↓
enrich.py → exact DOI Crossref/DataCite + optional review suggestions
   ↓
state.py → stable IDs, first-seen, new/updated/removed
   ↓
workflow.py → year/type/status selection
   ├── report.py → LaTeX → local XeLaTeX → PDF
   ├── JSON / BibTeX / source audit files
   └── export.py → public files OR encrypted metadata+PDF bundle
                      ↓
                web/index.html + app.js + styles.css
```

## Record representation

Each publication stores a stable `id`, title, ordered authors, category, date with preserved precision, `profile_year`, date source, optional publisher date and DOI metadata, venue, status, links, researcher attribution and source citations/fetch timestamps. `first_seen` and `last_changed` track collection history. Source records supply the original CV citation and category.

The data JSON has `publications` for the selected report and `catalogue` for all collected years. Web filters use `catalogue`. Bibliographic source authors are retained; publisher metadata fills missing fields. The collector never automatically discovers/imports a researcher by name.

## Matching

Same-DOI entries merge only if normalized titles are very similar. Distinct titles sharing a book-of-abstracts DOI stay separate. Entries without conflicting DOIs merge on exact normalized title + profile year + category. Normalization removes case, punctuation, whitespace and diacritics. Revised titles without a DOI are deliberately not fuzzy-merged.

Initial IDs hash DOI plus title, or title/year/category when DOI is absent. Reconciliation preserves an existing ID when a DOI is added and the prior record still matches. Meaningful changes include title/authors/date/DOI/venue/type/status/attribution/links/bibliographic fields and source citation changes. Fetch timestamps and caches do not by themselves mark a record updated.

Identical papers classified differently across profiles carry a warning when merged by DOI. Distinct chapters and conference editions remain separate unless the source supplies the same DOI and a matching title. DOI title conflicts remain evidence, do not change publication dates and are omitted from exported BibTeX DOI fields.

## Failure handling

A failed/private/layout-changed source is marked unavailable. A partially parsed source is marked partial. Existing records from that source are retained so a temporary error does not look like mass deletion. Records no longer listed after successful reads are absent from the new catalogue and reported in `changes.no_longer_listed`; the prior snapshot remains available locally.

If every source fails and there is no saved data, the run fails without replacing the output or establishing an empty baseline. A verified empty publication table is allowed. A successful collection is saved before report compilation so a TeX failure can be repaired with `report` without another network crawl. Atomic state writes prevent half-written JSON. A process lock serializes CLI and local-server builds against the same project.

## Local server

`server.py` serves an allowlist of static files from `web/` on 127.0.0.1. It never serves the project root. A single background job can collect or rebuild while the UI polls status. POST jobs require a random session token plus exact Origin and Host checks. The browser cannot choose arbitrary commands, paths or source URLs. This is a local tool, not a production internet-facing Python server.

Encrypted web exports disable browser-triggered jobs; use the CLI with `--encrypt` to preserve that mode. The server has no password database, shell command endpoint or external telemetry.

## Versioning

The CLI, package metadata, generated dataset, webpage and PDF identify version `1.1.1` and build `20261013.3`. Python packaging installs the CLI package; run from the supplied project folder so `config.toml` and `web/` are available. Full source is delivered, including all report-generation logic; no proprietary runtime is required.

## Scientific report and event timing

`events.py` resolves conference editions generically from explicit CV participation, Crossref event metadata and conference webpages. Optional Brave search discovers new webpage URLs. Accepted dates are cached with source evidence. `date` remains bibliographic; `activity_date` adds a sourced event-month fallback. Attendance is marked only from explicit participation entries. See `CONFERENCE_DATES.md`.

The PDF contains scientific-output totals, conference participation, publications and a linked alphabetical roster. Parsing statistics and collection diagnostics remain in local audit files. The web interface includes a persistent Light/Dark/System selector and contains no researcher publication-comparison chart.

## Encrypted CI state

`ci_state.py` packs only allowlisted catalogue state and hashed HTTP-cache filenames into an authenticated AES-GCM envelope with context `PublicationGroupCI:v1`. The Actions cache contains only `.ci-private/state.enc.json`; decrypted files exist on the ephemeral runner during collection. Restore authenticates the entire envelope and validates all file paths before writing; source files, credentials and lock files are excluded. A missing cache creates a baseline; a wrong key or damaged cache stops the workflow. Explicit `reset_state` is required to disregard an existing archive after changing the passphrase. Pages permissions belong only to the deployment job; deployment runs from the default branch.
