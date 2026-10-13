# How conference dates are found

Version 1.1.1 · build 20261013.3

The collector resolves conference **editions**, identified by venue name and year. No conference name or date is built into the resolver. A new conference does not require a new code rule.

## Resolution process

1. Check explicit dated conference-participation records on the configured public CVs. These also provide attendance evidence independently of publication authorship.
2. Reuse a sourced resolution from the local conference cache, or match an alternative name for the same edition.
3. Read the event start/end dates in verified DOI metadata, and query Crossref for the conference name and year when necessary.
4. Read conference links present in source records or optional website hints.
5. If `BRAVE_SEARCH_API_KEY` is configured, search for the conference website. Search results supply candidate URLs only; dates are extracted from the fetched pages, not from search snippets.
6. Read Schema.org Event `startDate`/`endDate`, or an unambiguous written date range in conference context. Match the conference name and edition year. Exclude submission, notification and registration deadlines, cancelled/postponed events, wrong editions and conflicting date ranges.

Each accepted result stores the source URL, extraction method, evidence and check time in `data/conference_dates.json`. Unresolved editions remain unresolved and are listed in the local audit. No January/June/default month is fabricated.

The delivered snapshot contains sourced resolutions for the four conferences represented by the 2026 contributions. These are cached results from actual conference webpages, not special conference rules. The same extraction code is tested against a previously unseen fictional 2031 conference.

## Automatic website discovery

Crossref and dated CV participation work without a search key. Searching the wider web for an arbitrary new conference website uses the optional Brave Search API.

Configure `BRAVE_SEARCH_API_KEY` in the environment of the collector. On GitHub Actions, add a repository secret with that name; the supplied workflow passes it to the collector. Do not put it in `config.toml`, source files or command arguments. API access requires your own provider account; no account or subscription was created during development.

Without a search key, Crossref, source-provided links, cached conference pages and CV participation can still resolve dates. If these sources do not supply a reliable date, the month remains unknown. Consequently, date resolution is evidence-based and cannot guarantee a date for every conference.

## Configuration

```toml
[events]
enabled = true
scope = "report"       # Resolve report period first; "all" checks the catalogue.
web_search = "brave"
lookup_limit = 12      # New/unresolved editions per run.
cache_days = 90       # Resolved editions; unresolved attempts retry after one day.
```

Rebuilding with `report` performs no web requests. It uses saved event evidence and explicit CV participation dates. `run` attempts new date resolution. The source cache and event-resolution cache are separate: `--refresh` refreshes HTTP responses used in a collection but does not discard resolved event evidence; to revisit a date, remove its generated cache entry or shorten `cache_days`.

A website hint can be provided when automated discovery cannot find the correct page. It supplies a URL, not a fixed date:

```toml
[[events.sources]]
venue = "A conference name exactly as listed on the CV"
year = 2027
url = "https://conference.example/"
```

The extractor still verifies the edition and reads the date from that page. This is optional; it is not a required step for every new conference when web discovery is configured.

## Publication date versus event date

The original bibliographic publication date remains in `date` and in BibTeX. A sourced event month is used as an `activity_date` fallback for a year-only conference paper, poster or abstract. A known publication month takes precedence. Journal articles, preprints and book chapters do not inherit conference dates.

The chart distinguishes publication months (blue) from conference months (green). Activity ordering uses this same date fallback. Each conference contribution shows its event dates separately. An individual's exact presentation day is never inferred from the event's start date.

The current report now dates 9 of its 12 outputs: 2 from publication metadata and 7 from conference dates. Three remain year-only.

## Attendance

Authorship or acceptance does not prove attendance. The report summarizes conferences with recorded contributions, and marks attendance confirmed only from an explicit public CV participation entry. The source CVs currently confirm an AWEC 2026 participation entry; the other event contributions do not automatically identify attendees.

## References

- [Crossref event-date filters](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/)
- [Schema.org Event](https://schema.org/Event)
- [Brave Search API authentication](https://api-dashboard.search.brave.com/documentation/guides/authentication)
- [AWEC 2026](https://awec2026.com/)
- [CONTROLO 2026 conference dates](https://controlo2026.likealot.pt/main-programme/)
- [Optimization 2026](https://optimization2026.iseg.ulisboa.pt/)
- [IFAC 2026 meeting and congress dates](https://ifac-control.org/participate-in-ifac/2026-ifac-council-and-related-meetings/)
