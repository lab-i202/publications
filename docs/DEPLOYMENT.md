# Automated publication collection and encrypted GitHub Pages deployment

Version 1.1.1 source, with hosted-macOS collection workflow.

## Expected behavior

`.github/workflows/main.yml` has manual dispatch and a daily schedule at
06:17 UTC. GitHub Actions schedules can be delayed or disabled after extended
repository inactivity, so review the Actions run history from time to time.
The workflow processes the eleven configured public CiênciaVitae profiles.

1. GitHub-hosted macOS collects profiles, verifies HTTPS with system `curl`,
   preserves prior profile records on partial/unavailable reads, detects changes,
   enriches DOI metadata, and saves an AES-GCM-encrypted state snapshot.
2. The snapshot is transferred as an **encrypted** artifact to a fresh Ubuntu
   job. The two jobs use the same GitHub Actions secret but never transfer
   plaintext state as an artifact.
3. Ubuntu decrypts the state on its temporary runner, builds the publication
   report without recollecting, compiles the PDF, and encrypts the catalogue,
   bibliography and PDF into the website bundle.
4. Only six allowlisted static files, including `bundle.enc.json`, are
   deployed. The deployment job does not upload plaintext publication data.

A scheduled run uses a refreshed HTTP fetch, so new public CV entries are
eligible to be detected even when the previous collection was recent. This
may generate substantial HTTP traffic; respect upstream rate limits and adjust
frequency or refresh policy if the source operator requires it.

## Configure

1. Upload the **source-only** code, never the original snapshot archive
   containing `output/`, `data/` or plain `web/publications.json`.
2. In **Settings -> Pages**, select **GitHub Actions** as the source.
3. In **Settings -> Secrets and variables -> Actions**, create the repository
   secret `PUBGROUP_PASSPHRASE` containing a random, private password. The
   application's minimum length is 16, but use much more entropy.
4. Ensure you have **only one** deployment workflow enabled. In this version
   it is `.github/workflows/main.yml`; remove obsolete `pages.yml` if present.
5. In **Actions -> Monitor authors and deploy encrypted Pages**, run the
   workflow on `main`, with `reset_state` false for ordinary runs. Use
   `reset_state` only deliberately after rotating the password; it resets
   first-seen/change history.

The website URL for repository `lab-i202/publications` is
`https://lab-i202.github.io/publications/`. Each authorized visitor enters
*the same* passphrase to decrypt the bundle locally in their browser.

## Limits

- **Hosted macOS connection is not yet verified.** Mac runners use a different
  TLS trust environment from Ubuntu, but they are not guaranteed to fix the
  public CiênciaVitae server's incomplete or otherwise untrusted chain. A
  live successful job is the required acceptance test.
- **Actions caches are best effort.** They can be deleted or evicted, so
  encrypted state stored only in the cache is not reliable indefinite archival
  storage. Keep a private, independent backup if durable historical change
  tracking matters.
- Daily polling does not guarantee complete publication coverage. The source
  depends on authors keeping their *public* CiênciaVitae profiles up to date.
  The first successful run establishes a baseline, so previously listed works
  are not incorrectly presented as new discoveries.
- The current crawler parses public `/portal/` HTML. A site redesign may
  require parser maintenance. The official CiênciaVitae API is a possible
  longer-term source, subject to obtaining valid access credentials.
- Public repositories expose source files, author IDs in `config.toml`, and
  GitHub Actions logs. Do not upload sensitive records or plaintext snapshots.
- GitHub Pages is public hosting, not a login service. The passphrase protects
  the encrypted bundle, not access to the code or downloaded ciphertext.
- GitHub Actions administrators / maintainers who can modify workflows and
  deploy scripts are in the trust boundary. Restrict write access.

## Files deployed

```
index.html
app.js
styles.css
.nojekyll
manifest.json
bundle.enc.json
```

No `publications.json`, PDF, BibTeX, HTTP cache, or decrypted state is deployed
as a separate file. The encrypted bundle contains PDF and bibliography.

## References

- [GitHub-hosted runner images](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [GitHub Actions schedules](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule)
- [GitHub Actions secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions)
- [GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

## Website-triggered refresh

Authorized website users can now request new collection runs with **Refresh sources**, after setting up the external Cloudflare backend. See [WEB_REFRESH.md](WEB_REFRESH.md) for complete deployment/security instructions. The backend uses the same shared passphrase and a server-only GitHub token. An additional public GitHub Actions variable `PUBGROUP_REFRESH_API_URL` configures the origin and CSP. Without that variable the static website retains its old manual-command fallback.
