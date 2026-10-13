# Feature tutorials

Version 1.1.1 · build 20261013.3

## Produce the end-of-year report

1. Check the researcher list in `config.toml`.
2. Run `python3 -m pubgroup run --refresh --period 2026`.
3. Review `output/audit/sources.json` for unavailable/partial sources and `output/audit/doi-checks.json` for title conflicts.
4. Open `output/pdf/publications.pdf`. Copy it to an archive folder if you want to retain that edition.

The report contains scientific output, conference participation and an alphabetical researcher/CiênciaVitae roster. It contains the selected year's full list, not only newly detected entries. Accepted/in-press/unspecified records are included by default and labelled. Set `include_statuses` if your institution requires a narrower definition.

## See new publications

Run the collector again after researchers update their public profiles. Open the website and use **New only** in the publication filters. Select **All years** to see older papers newly added to a profile.

The first collection establishes a baseline. Refreshing unchanged records produces zero new records. “New” refers to detection, not publication date. Rebuilding a report keeps the last collection's change summary. Each subsequent collection compares against the immediately previous saved collection; it does not accumulate unread notifications.

## Read, copy and export

Run `python3 -m pubgroup serve`, then visit <http://127.0.0.1:8765>.

Search by title, author, venue or DOI. Filter by year, publication type, researcher or status. **Open publication** opens the source link in a new tab. An unavailable paper/poster link is labelled; the tool does not substitute an unrelated file.

**Copy BibTeX** copies one record. If the browser blocks clipboard access, it downloads a `.bib` file instead. **Export filtered BibTeX** exports every matching record, including those not currently rendered due to pagination. Expand **Citation, dates & sources** to inspect the generated entry, source profiles and date policy.

**Download PDF** downloads the prepared report with its labelled period. Browser search/type filters do not rewrite that PDF. In the local server, choose a year and click **Build PDF for selected year** to generate that year's report. The build uses configuration type/status filters. On GitHub Pages, use the CLI or manual Actions workflow to generate a different report.

## Understand the counts

**Records** counts each combined catalogue record once. **Conference records** counts conference papers, posters and abstracts. **Researchers** counts configured profiles listing one or more matching records. **New** counts records first seen since the last saved collection.

The monthly chart separates known publication months from sourced conference months. With All years selected, January combines January records from all matching years. There are no researcher comparison charts.

## Work without the internet

`python3 -m pubgroup report --period 2025` rebuilds from saved state without making requests.

`python3 -m pubgroup run --offline` reparses cached HTML and checks cached DOI metadata. It is useful for verifying parser changes. Cached timestamps remain visible; an offline run is not a fresh source check.

## Protect the hosted library

Install `requirements.txt`, then run `python3 -m pubgroup report --period current --encrypt`. Use a long random passphrase of at least 16 characters. Serve `web/` over localhost or HTTPS. Enter the same passphrase in the unlock form. It is used only in the browser and is not stored in localStorage.

The encrypted bundle includes the full catalogue and the prepared PDF. **Lock** reloads the page and releases the app's decrypted state. Files already downloaded remain on your device. Decryption does not give access to a local collector from the hosted site.

## Add or correct records

Correct the publication on its original public CiênciaVitae profile, then run `--refresh`. Optional Crossref title suggestions can help you investigate a missing DOI, but should be confirmed by title, authors and edition before adding it to the source. This release deliberately has no manual record editor that would compete with researchers' own CVs.

## Choose a theme

Use the Theme selector in the top bar to choose Light, Dark or System. The choice is saved in this browser. It is available before and after unlocking an encrypted library. Only the theme preference is stored; decrypted publication data is not.

## A newly added conference

Run the collector normally. It detects the new edition by venue and year, checks CV participation dates and Crossref metadata, and follows conference links. With a Brave API key configured, it also discovers conference websites automatically. Unambiguous sourced dates fill the activity month; missing/conflicting dates stay unknown. See `CONFERENCE_DATES.md` for setup and limits.
