# Sources, matching and coverage

Version 1.1.1 · build 20261013.3 · checked 13 October 2026

## Live profile audit

All eleven supplied profile IDs were read through their canonical public `/portal/` URLs. The original `/pt/F21A-4DC9-91B8` URL is configured as its equivalent portal profile. This is a live HTML check, not a reconstruction from search-engine snippets.

| Researcher | Ciência ID | Parsed records |
| --- | --- | ---: |
| Conrado José Correia Guimarães Martins da Costa | [F21A-4DC9-91B8](https://www.cienciavitae.pt/portal/F21A-4DC9-91B8) | 7 |
| Gabriel Moura Fernandes | [9A13-2FC9-CB20](https://www.cienciavitae.pt/portal/9A13-2FC9-CB20) | 16 |
| Rui Carvalho da Costa | [7A11-FA9D-70BC](https://www.cienciavitae.pt/portal/7A11-FA9D-70BC) | 15 |
| Luís Augusto Correia Roque | [261D-86F7-A774](https://www.cienciavitae.pt/portal/261D-86F7-A774) | 47 |
| Fernando Armenio da Costa Castro e Fontes | [3716-EBD5-6CFE](https://www.cienciavitae.pt/portal/3716-EBD5-6CFE) | 41 |
| LUÍS TIAGO DE FREIXO RAMOS PAIVA | [891A-BDE5-9FD8](https://www.cienciavitae.pt/portal/891A-BDE5-9FD8) | 66 |
| Huu Thien Nguyen | [D117-BD12-20F8](https://www.cienciavitae.pt/portal/D117-BD12-20F8) | 13 |
| Amit Shivam | [1316-1F11-27BD](https://www.cienciavitae.pt/portal/1316-1F11-27BD) | 11 |
| Sofia Oliveira Lopes | [E31D-A8CB-82D3](https://www.cienciavitae.pt/portal/E31D-A8CB-82D3) | 34 |
| Manuel Côrte-Real de Matos Fernandes | [3819-3691-B535](https://www.cienciavitae.pt/portal/3819-3691-B535) | 29 |
| Sérgio Vinha | [E01E-894D-7B6F](https://www.cienciavitae.pt/portal/E01E-894D-7B6F) | 19 |

The source audit found **298 profile records**, combined into **215 catalogue records** under the documented matching rules. The default 2026 report contains **12 records**: 4 conference papers, 2 journal articles, 2 conference posters, 2 preprints, 1 book chapter and 1 conference abstract. Status labels are 2 published, 2 in press, 1 accepted and 7 unspecified. Nine of the 12 outputs have a publication or sourced conference month; three remain undated within the year.

The totals are a snapshot of public CV entries, not a claim of exhaustive output or group membership at publication time. Author attribution comes from the configured profiles that list each record. Some researchers list only a subset of their work.

## UPWIND context and linked library

The supplied [team page](https://www.upwindresearchproject.com/about) is a group reference, not an individual CiênciaVitae profile. It was checked separately. The [publications page](https://www.upwindresearchproject.com/publications) links to the public [UPWIND Zotero library](https://www.zotero.org/groups/5341747/upwind_site/library).

The Zotero API check returned **67 bibliographic entries**. **39 matched** a title/DOI in the collected catalogue and **28 were unmatched**. Unmatched does not necessarily mean missing: editions, revised titles, theses, records by other authors and differently classified outputs need checking. These entries appear on the website's Sources & changes panel and in `output/audit/zotero-review.json`. They are deliberately excluded from publication totals until verified and added to a configured profile. This check can be disabled in configuration.

## DOI databases

The collector queried Crossref by exact DOI and used DataCite when a record was unavailable there. In this snapshot, 120 DOI-bearing catalogue records were checked: 114 passed title comparison and 6 have a title conflict. Matching metadata fills missing venue/publisher/pages/volume and eligible dates; it does not overwrite explicit CV status or researcher attribution.

Title markup such as MathML is stripped before comparison. Title similarity below 0.82 prevents application of DOI metadata. Whole-book/abstract-volume DOIs and clearly unrelated DOIs remain source evidence and require review. These DOI fields are omitted from exported BibTeX to avoid sending readers to a different paper. Source links remain inspectable.

Concrete issues found include a 2019 kite-guidance entry pointing to a 2002 AIAA flight-path-control DOI, an AWEC abstract pointing to an entire proceedings/abstract volume, and an old book-chapter entry pointing to a different later chapter. Full details, source citations and DOI metadata are in the audit output. The tool reports disagreements instead of silently changing the publication's identity.

Optional Crossref title searches return candidates only. There is no name-based automatic import from OpenAlex, ORCID, Scopus or Google Scholar. Public ORCID IDs are preserved for future verified integrations; they are not used as permission to scrape restricted databases.

## Matching rules

1. Normalize DOI case/URL form and title case, punctuation, accents and whitespace.
2. Merge identical DOIs only when normalized title similarity is at least 0.90. A DOI shared by very different titles does not merge them.
3. Otherwise merge exact normalized title + profile year + category, provided known DOIs do not conflict.
4. Keep distinct publication kinds/years/DOIs as separate editions. A chapter published after a conference presentation can be a separate record.
5. Preserve every listing profile and original source citation. Category/date disagreements remain warnings.

These rules are conservative, but automated matching cannot prove that every edition/version has been identified perfectly. Review the bibliography before submitting a formal institutional report.

## Source access

CiênciaVitae's robots file allows `/portal/` and disallows `/cv/`. The collector checks these rules and reads only public portal pages. It verifies identity against the supplied Ciência ID and requires a publication section/table to mark a read successful. It does not treat a login, unavailable profile or unexpected layout as an empty CV.

Raw HTML caches contain the complete public page and can include contact details. Only professional identity, ORCID and publication data enter normalized output. Do not publish raw caches.

## Documentation references

- [CiênciaVitae API documentation](https://api.cienciavitae.pt/docs/) — an official API exists; this release uses verified public portal HTML rather than assuming API credentials.
- [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/)
- [DataCite REST API](https://support.datacite.org/docs/api)
- [Zotero Web API v3](https://www.zotero.org/support/dev/web_api/v3/basics)
