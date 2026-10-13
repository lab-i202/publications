# Verification results

Version 1.1.1 · build 20261013.3 · 13 October 2026

## Source snapshot

The eleven public profiles supplied for this project produced 298 publication entries and 215 combined catalogue records. The current-year report contains 12 scientific outputs. Bibliographic DOI checks and unmatched Zotero entries remain available in local audit files; they are not included as parsing statistics in the scientific report.

Four conference editions are represented by seven current-year papers, posters and abstracts. The generic webpage extractor resolved their dates from sourced pages. Seven outputs now use a verified conference month as an activity fallback, two have publication months, and three remain year-only. Original bibliographic dates and BibTeX years are preserved.

Explicit CV conference-participation entries are collected separately. The supplied CVs contain a dated AWEC 2026 participation record, which confirms attendance independently of publication authorship. Authorship or acceptance alone is not marked as attendance.

Repeating collection from unchanged cached sources produced zero new, updated or removed publications. Conference evidence and theme preferences do not create false new publications.

## Automated checks

35 regression tests passed with Python 3.12.14 and the optional encryption dependency installed. The core collector and report builder also run under the system Python 3.14 without third-party Python packages.

The suite covers parsing, publication chronology, DOI/title matching, baseline changes, failed-source retention, report periods, encryption and concurrency. New tests cover:

- A previously unseen fictional conference discovered through a mocked search API and generic Schema.org Event extraction.
- Crossref event dates without any search key.
- Explicit CV participation dates without a DOI or search key.
- Submission-date rejection, conflicting dates, wrong editions, cancelled events and reused acronyms with different full names.
- Original publication-month preservation, non-conference dates and event-month activity ordering.
- Uppercase name normalization and API secret headers passed through stdin rather than process arguments.

The resolver contains no AWEC name/date condition or conference-specific alias table. The current resolved dates are generated cache entries carrying source evidence, not code rules.

Python compilation and JavaScript syntax checks passed.

## PDF checks

The revised current-year PDF has 7 A4 pages; the all-years PDF has 45. Both compiled twice with XeLaTeX and were rendered with Poppler for visual inspection. The current source also compiled successfully with the desktop editor's built-in compiler.

The report contains scientific-output totals, a two-colour activity chart, conference participation, publications and an alphabetical researcher roster with clickable CiênciaVitae links. Publication blocks stay together. The PDF has no researcher publication-count table, Parsed/Unreadable columns, DOI-check summary, baseline report or parsing-status section. Actual bibliographic author names remain in publication citations.

PDF text assertions checked that the removed diagnostics were absent and that the requested scientific sections were present. All pages were inspected in contact sheets, with larger views for the current report's main sections. The current build log showed no overfull boxes, missing glyphs or warnings.

## Browser checks

The revised site was checked in the in-app browser:

- Researcher dropdown is alphabetical and uppercase-only names use normal capitalization.
- The researcher comparison chart is absent.
- The monthly chart reports three unresolved months and distinguishes publication and event months.
- Sources & changes is a simple linked list of researcher profiles, reference services and event-date webpages, with a short collection-change summary.
- Explicit Light and Dark choices work; Dark remains selected after reload. System remains an available option.
- No JavaScript errors appeared during these checks.

## Limits

No Brave API credential was provided. Its discovery integration was verified with a mocked API response, not a paid live search request. Real webpage extraction and cached-source runs were verified. Without a search key, Crossref, explicit CV participation, source links and existing evidence can resolve dates; arbitrary new websites may remain undiscovered.

A date is not guaranteed for every conference. Ambiguous or unavailable dates remain unknown. Dated attendance entries do not imply that every coauthor attended. Current-year membership and completeness of researchers' public profiles are not inferred.

The GitHub workflow includes an optional Brave API secret, but no repository was provided and no remote deployment was performed. Local preview servers are stopped after verification; use `python3 -m pubgroup serve` to reopen the tool.

## Public-repository security update (1.1.1)

All 40 tests passed with the encryption dependency installed. Five new tests cover encrypted state/cache roundtrip, absence of plaintext contents and keys in the envelope, wrong-key and modified-ciphertext rejection, path traversal and symlink rejection, separate website/state cryptographic contexts and missing-cache baselines. A source-only archive was checked for excluded data, caches, PDF/BibTeX, generated web files and secret files. The workflow was inspected locally; no repository was created and no live GitHub Actions or Pages run has been performed.
