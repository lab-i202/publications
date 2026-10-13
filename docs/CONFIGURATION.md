# Configuration

Version 1.1.1 · build 20261013.3

Edit `config.toml`, then run `python3 -m pubgroup run`. `--config /path/to/file.toml` uses paths relative to that file's folder. Keep the config in the project folder so the web assets are found.

## Report period

```toml
[report]
period = "current"      # Europe/Lisbon current year
start_year = 2020       # Used only for period = "range"
end_year = 2026
```

Supported periods: `"current"`, `"all"`, `"range"`, or `"2025"`. `--period` overrides the configured value for that invocation. A range includes both endpoints. Undated records appear only in all-years reports.

## Date policy

`date_basis = "profile"` is the default. It keeps the CV year and fills in a month/day from a matching DOI only if its year agrees. A disagreement is recorded as a warning.

`date_basis = "publisher"` uses the verified DOI publication date when available. This can move a conference record into a later year when its proceedings appeared later. Deposit, creation and indexing dates are never used as publication dates. Records without verified DOI dates use the profile year.

Year-only conference contributions use a sourced event month for activity ordering when available; other year-only outputs sort after dated outputs in their year. This order does not assert that the year-only records were actually published earlier or later than the others.

## Categories and status

```toml
include_types = ["conference", "journal", "chapter"]
include_statuses = ["published"]
```

Empty lists include every value. Categories: `conference`, `journal`, `chapter`, `book`, `poster`, `abstract`, `thesis`, `preprint`, `report`, `other`.

Statuses: `published`, `accepted`, `in press`, `unspecified`. **A DOI does not automatically turn an accepted or unspecified CV entry into a published one.** Status is taken from the explicit source label. For a report of papers known to be published, use the status filter, understanding that unlabelled published papers can then be excluded.

Configuration filters affect the PDF and selected report bibliography. The web catalogue remains available across all years; browser filters are independent, and its PDF button always labels the actual report period.

## Researchers

```toml
[[researchers]]
id = "9A13-2FC9-CB20"
url = "https://www.cienciavitae.pt/portal/9A13-2FC9-CB20"
```

Use the canonical portal URL, even if the original link used `/pt/`. IDs must be unique. Names and public ORCID identifiers are read from the profile, not guessed from the team page.

Removing a profile from configuration removes its attribution on the next successful collection. Copy `data/` before changing group membership if you need to preserve a historical roster. There is no automatic group-membership date filter.

## Network

`timeout_seconds = 30`, `retries = 2`, `delay_seconds = 0.35`, `cache_hours = 24`.

The collector checks robots.txt before reading profiles, observes crawl delay, retries transient failures with bounded backoff, and honours numeric Retry-After values up to 60 seconds. HTTP 401/403/404 is not retried. Set `contact_email` to a real contact address if you want an identifiable Crossref user agent. Leave it blank otherwise.

`--refresh` ignores fresh caches. `--offline` reads saved HTTP responses only; a missing response is logged as unavailable. `report` needs only saved state, not raw caches or internet.

## Cross-references

`enrichment.enabled = true` performs exact DOI lookup for the entire catalogue. Existing API responses are cached, so subsequent runs are faster. `enrichment.title_candidates = true` also searches titles without DOIs in Crossref; results go to `output/audit/candidates.json` and require human review. They are never imported automatically. The optional title search makes more requests.

The supplied UPWIND publications page links to Zotero group `5341747`. `enrichment.review_zotero = true` reads its public API and lists unmatched records for review; set it to false to skip this supplementary check. Change `zotero_group_id` only to a known public group library. It does not import records or change author attribution.

## Outputs

`output.directory = "output"`, `output.web_directory = "web"`, `output.compile_pdf = true`.

Use `--no-pdf` to write LaTeX when XeLaTeX is unavailable. The website then disables its PDF download. Encryption is chosen per command using `--encrypt`; repeat it whenever rebuilding an encrypted website, since ordinary exports produce public plaintext data. The local server disables rebuild buttons for encrypted exports to avoid inadvertently changing export mode.

## Conference dates and attendance

See [Conference date discovery](CONFERENCE_DATES.md). The resolver is generic; cached event metadata is not a conference-specific rule. Configure the optional search API in the environment, or use Crossref, explicit CV participation dates and source links.
