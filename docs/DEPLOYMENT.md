# GitHub Pages and encryption

Version 1.1.1 · build 20261013.3

Use a **public code repository and an encrypted website export**. GitHub Pages hosts the interface and ciphertext; visitors enter the group's shared passphrase to decrypt the catalogue, bibliography and PDF in their browser. The passphrase is not included in the website.

No repository has been created or published during development. These steps deploy to a repository you choose.

## 1. Upload only the source

Use `publication-group-1.1.1-build-20261013.3-source-only.zip` from `output/release/`. Extract it into a new folder. It contains the complete code, documentation, tests, configuration and frontend assets, but no collected data or PDF. The profile IDs and group name in `config.toml` will be public.

On GitHub, create a new **public** repository, for example `publications-i202`. Leave the initial README, licence and .gitignore options unchecked because the source already has its own files.

In a terminal, enter the extracted `publication-group-1.1.1` folder. Replace `YOUR-USERNAME` and `YOUR-REPOSITORY` below with the repository owner and name:

```sh
git init -b main
git add .
git status --short
git diff --cached --name-only
git commit -m "Add publication collector and encrypted Pages site"
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

Before the commit, review the staged filenames. There should be no `data/`, `cache/`, `output/`, `.ci-private/`, `.env`, PDF, BibTeX or generated `web/publications.json`. Upload the extracted source files, not the ZIP itself. GitHub Desktop is another option: add the extracted directory, publish it, and check the same file list before committing. Ensure the hidden `.github/workflows/pages.yml` and `.gitignore` are included.

**Do not upload a `-snapshot.zip` archive.** Snapshot archives contain plaintext example data and reports. Browser uploads and release attachments do not apply `.gitignore`. Likewise, hiding or ignoring a file does not remove it if it was already committed.

## 2. Enable Pages

In the repository, go to **Settings → Pages → Build and deployment → Source**, and select **GitHub Actions**. The supplied workflow builds and uploads the site; no `gh-pages` branch is needed.

Official instructions: [custom GitHub Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## 3. Create the shared secret

Generate a long random passphrase in a password manager, preferably at least 32 random characters. The application's minimum is 16 characters; the minimum does not guarantee strength. Keep the phrase privately and share it only with intended readers through your usual private channel.

Go to **Settings → Secrets and variables → Actions → New repository secret**:

- Name: `PUBGROUP_PASSPHRASE`
- Value: your generated passphrase

Do not put it in `config.toml`, JavaScript, README, Git history, an issue or a workflow input. The workflow receives it through an environment variable and uses it for both the website bundle and persistent collection-state cache. It is required for this workflow even if you explicitly select a publicly readable export.

Optionally add `BRAVE_SEARCH_API_KEY` as another repository secret to enable discovery of new conference websites. It is not needed to collect the profiles or generate reports. See [conference date discovery](CONFERENCE_DATES.md).

Official instructions: [GitHub Actions repository secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).

## 4. Publish

Go to **Actions → Collect publications and deploy Pages → Run workflow**. Run from the repository's default branch, normally `main`.

- `period`: `current` for this year; `all` for all years; `2025` for one year. `range` uses the start/end years in `config.toml`.
- `encrypted`: **leave checked**. Unchecking it intentionally publishes the readable catalogue, bibliography and PDF.
- `fresh`: check to refetch profile and DOI responses instead of using fresh HTTP cache entries.
- `reset_state`: leave unchecked. This deliberately discards the restored baseline and is useful after changing the passphrase.

The runner installs Python and LaTeX, restores encrypted state, runs regression tests, collects the public source records, compiles the PDF, encrypts the export and state, and deploys a fixed allowlist. The first run can take several minutes because it installs TeX and fetches sources.

When the deployment finishes, open its Pages URL, usually `https://YOUR-USERNAME.github.io/YOUR-REPOSITORY/`. Enter your passphrase in the unlock form. Search, filters, dark mode, links, BibTeX copy and PDF download work after unlocking. The phrase is not sent by that form or stored in browser localStorage.

## 5. Update the website

Run the same workflow whenever you want a new collection/report. Pages itself serves static files; it cannot run Python, crawl profiles or compile LaTeX when a visitor opens it. Update configuration through a source commit, then rerun the workflow.

The first collection establishes a baseline and shows zero new records. Later runs compare with the restored state. Actions caches are best-effort and can be evicted; a missing cache starts another baseline. For durable historical tracking, retain a private backup of local `data/` or use a controlled persistent private store.

To change the phrase, update the `PUBGROUP_PASSPHRASE` secret and run with `reset_state` checked. This publishes a new encrypted bundle and starts a new baseline. A changed phrase or damaged restored cache without a reset causes authentication to fail and stops deployment; there is no silent plaintext fallback. Previously downloaded exports remain decryptable with their old phrase.

## What is public and what is encrypted

| Item | Exposure with the recommended setup |
| --- | --- |
| Python code, HTML, CSS, JavaScript, docs, configuration | Public, including configured researcher/profile IDs |
| Aggregate catalogue, BibTeX and report PDF | Encrypted together in `bundle.enc.json` |
| Persisted collection state and raw HTTP responses | Encrypted in the Actions cache; decrypted temporarily on the runner |
| Shared passphrase and optional search API key | GitHub Actions secrets; absent from source and deployment files |
| Workflow logs | Public progress, profile IDs and aggregate counts; not a place for confidential details |
| Local `data/`, `cache/`, `output/` and snapshot archives | Plaintext on your computer; excluded from the source upload |
| Original CiênciaVitae and conference webpages | Retain their original public visibility |

The deployment contains only `index.html`, `app.js`, `styles.css`, `.nojekyll`, `manifest.json` and `bundle.enc.json` in encrypted mode. No recursively copied workspace, plaintext report or raw profile HTML is uploaded as a Pages artifact.

GitHub explicitly warns that repository readers can access Actions caches. Version 1.1.1 stores **only encrypted state** there; version 1.1.0 cached plaintext state and HTTP responses. If an earlier workflow has already run in a public repository, delete its old `publications-state-*` caches under **Actions → Caches**. The new workflow never restores those old cache keys. This cannot undo copies someone already downloaded.

Source: [GitHub cache access and security](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching).

## How encryption works

SHA-256 is a one-way hash, not reversible encryption. This tool uses AES-256-GCM authenticated encryption, with a new 16-byte salt and 12-byte nonce for every envelope. PBKDF2-HMAC-SHA256 with 600,000 iterations derives a 256-bit key from the phrase. The browser and Python use authenticated context `PublicationGroup:v1`; the state cache uses separate context `PublicationGroupCI:v1`.

The PDF is inside the encrypted bundle and becomes a downloadable browser Blob only after decryption. The browser requires HTTPS or localhost for Web Crypto. A wrong phrase or modified ciphertext fails authentication.

This is a shared passphrase, rather than a WebAuthn passkey or individual accounts. Anyone can download the ciphertext and try guesses offline, so use a random phrase. Authorized readers can save or forward decrypted files. Rotation protects new exports but cannot revoke existing downloaded copies. Bundle size and the existence of the website remain public.

Keep repository write access limited to trusted maintainers: someone who can alter a workflow or browser code can change how secrets and decrypted data are handled. This setup trusts GitHub's runner and hosting, workflow dependencies and maintainers. If the roster itself must be confidential, the supplied public `config.toml` is unsuitable; put configuration in a private build environment too.

For individual accounts, revocable permissions or sensitive nonpublic records, run collection in a private environment and use authenticated hosting/backend access. Ordinary GitHub Pages should be treated as publicly reachable; GitHub documents restricted visibility for supported Enterprise Cloud organization-owned private/internal project sites.

Sources: [Pages visibility](https://docs.github.com/en/enterprise-cloud@latest/pages/getting-started-with-github-pages/changing-the-visibility-of-your-github-pages-site), [Web Crypto key derivation](https://developer.mozilla.org/en-US/docs/Web/API/SubtleCrypto/deriveKey), [Web Crypto encryption](https://developer.mozilla.org/en-US/docs/Web/API/SubtleCrypto/encrypt).

## Troubleshooting

- **No workflow listed:** check that `.github/workflows/pages.yml` was committed and Actions is enabled.
- **Passphrase configuration error:** check the exact Actions secret name and provide at least 16 characters.
- **State authentication failed after changing the phrase:** rerun with `reset_state` checked. To preserve the existing baseline, decrypt/re-encrypt it privately instead of resetting.
- **Deployment blocked:** ensure Pages source is GitHub Actions and the default branch/environment is allowed to deploy.
- **Wrong phrase in the browser:** use the exact phrase from the latest successful deployment; a new secret alone does not update a previously deployed bundle.
- **No new-record history:** a first run, cache eviction or explicit reset creates a baseline. Back up state privately if history must be durable.
- **Confidential files were committed:** stop publishing them, remove exposed files from history/artifacts/caches as appropriate and rotate any exposed secret. Merely adding `.gitignore` is insufficient.
