# Changelog

## 1.1.1 — build 20261013.3 — 2026-10-13

- Fixed plaintext collection-state and raw-CV caching in the Pages workflow. Actions now caches only an authenticated encrypted envelope, with a separate cryptographic context from the web bundle.
- Added state restoration checks for wrong keys, altered ciphertext, path traversal and symbolic links; preserved change tracking between cached runs.
- Restricted deployment to the default branch and scoped Pages write permissions to the deployment job.
- Added a reset-state option for passphrase changes and separate source-only/snapshot release filenames.
- Expanded deployment documentation with public-repository setup, upload boundaries and secret handling.
- Passed 40 regression tests. Live GitHub deployment remains to be performed in the user's chosen repository.

## 1.1.0 — build 20261013.2 — 2026-10-13

- Reworked PDF as a scientific production report; removed parsing tables, researcher publication counts and collection diagnostics.
- Added conference participation and an alphabetical researcher roster with CiênciaVitae links.
- Added generic conference-date discovery through Crossref event metadata and webpage extraction, with optional Brave search for new websites. No conference-specific date rules.
- Added sourced event-month fallback, a two-colour monthly chart, and retained original bibliographic dates.
- Removed the researcher comparison chart and simplified Sources & changes to referenced webpages.
- Added persistent Light/Dark/System theme selection and uppercase-only name normalization.
- Added regression tests for unseen conferences, date ambiguity, submission deadlines, event editions and secret-header handling.


## 1.0.0 — build 20261013.1 — 2026-10-13

- Added a Python 3.11+ collector for the eleven provided public CiênciaVitae profiles.
- Added quoted/italic title parsing, publication-section isolation, identity checks and rejection auditing.
- Added DOI/title/year/type matching, including protection against shared book-of-abstracts DOIs.
- Added exact Crossref and DataCite metadata checks and optional title suggestions requiring review.
- Added a read-only comparison of the UPWIND-linked public Zotero library, listing unmatched entries for review.
- Added year precision, CV/publisher date policies, chronology, current/year/range/all filters and article-number regression protection.
- Added persistent baseline, first-seen dates, new/updated/removed summaries and failed-source retention.
- Added XeLaTeX reports, BibTeX and JSON exports with source evidence.
- Added a responsive light/dark web library using the supplied styling reference.
- Added local refresh/report jobs with loopback binding, Host/Origin validation and request tokens.
- Added optional AES-256-GCM/PBKDF2 encrypted static exports protecting both metadata and report PDF.
- Added manual GitHub Pages workflow, documentation and regression tests.
