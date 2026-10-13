# Website-triggered collection — deployment and security

This module adds **authenticated manual refresh** to the encrypted GitHub Pages
site at `https://lab-i202.github.io/publications/`. Scheduled GitHub Actions
collection is retained. The site remains static; a Cloudflare Worker sends a
GitHub Actions `workflow_dispatch` request when an authorized reader clicks
**Refresh sources**.

## Behavior

1. The visitor opens GitHub Pages and unlocks the AES-256-GCM bundle locally.
2. On **Refresh sources**, the browser sends that passphrase over HTTPS to a
   dedicated Worker. Until this click, the passphrase stays in the browser.
   The browser retains the passphrase in JavaScript memory **only until reload**
   (not in Local Storage, session storage, or cookies).
3. The Worker checks the exact configured origin and authorizes with a copy of
   the same long random passphrase stored as a **Cloudflare secret**.
4. A SQLite-backed Durable Object enforces 8 attempts/IP/10 minutes and a
   global 15-minute cooldown. Counters contain HMAC-derived IP identifiers,
   not readable IP addresses. An in-object request queue serializes dispatches.
5. The Worker uses a **server-only** fine-grained GitHub token to initiate the
   existing `main.yml` workflow with `fresh=true`. No GitHub token reaches JS.
6. The browser checks the published `manifest.json` revision every 15 seconds,
   for up to 20 minutes. When a new encrypted bundle appears, it decrypts that
   bundle locally, updates the visible catalogue and PDF, and reports success.

The Worker reports *accepted* once GitHub accepts the request, not when the
collection is complete. GitHub may fail because its hosted macOS runner cannot
access the source or for another reason. The browser reports an update only
after a new encrypted deployment is verified and decrypted.

## Prerequisites

- GitHub repository `lab-i202/publications`, on branch `main`, with the entire
  source-only project, `.github/workflows/main.yml`, and GitHub Pages enabled
  with **GitHub Actions** as the source.
- Repository Actions secret `PUBGROUP_PASSPHRASE` (64-character random string
  recommended). It MUST equal the Cloudflare `REFRESH_PASSPHRASE` secret.
- Node.js/npm on your Mac and a Cloudflare account supporting Workers and
  SQLite-backed Durable Objects.
- A GitHub fine-grained personal access token belonging to someone with the
  rights required to run Actions in `lab-i202/publications` (organizational
  approval may be required).

## Step 1 — Create the GitHub API token

Open `https://github.com/settings/personal-access-tokens/new`.

- Token name: e.g. `Publication Group refresh backend`.
- Resource owner: `lab-i202`.
- Repository access: **Only select repositories** → `publications`.
- Repository permissions: **Actions: Read and write** (fine-grained permission
  `Actions: write` is required for workflow dispatch).
- Give the token an appropriate expiry and store it in Apple Passwords.
- Click **Generate token** and copy the token; do **not** commit it, paste it
  in JavaScript or add it as a GitHub Pages variable.

GitHub may require organization approval before the fine-grained token is
usable. If GitHub returns 403, verify approval, token expiry and permissions.
A GitHub App installation token is an alternative to manually rotating PATs,
but is not implemented here.

## Step 2 — Deploy Cloudflare backend

From a Terminal in the extracted complete project folder:

```sh
cd refresh-backend
npm install
npx wrangler login
npx wrangler deploy
```

If using a Cloudflare organization or a different website, first update
`wrangler.jsonc` values: `ALLOWED_ORIGIN`, `GITHUB_OWNER`, `GITHUB_REPO`,
`GITHUB_REF` and `GITHUB_WORKFLOW`.

Then securely set both secrets:

```sh
npx wrangler secret put REFRESH_PASSPHRASE
npx wrangler secret put GITHUB_DISPATCH_TOKEN
```

For `REFRESH_PASSPHRASE`, paste the **exact** value already stored in GitHub
Actions `PUBGROUP_PASSPHRASE`. For `GITHUB_DISPATCH_TOKEN`, paste the GitHub
fine-grained token. Do not type either secret in command-line arguments.

Wrangler prints a public HTTPS Worker URL like:

`https://pubgroup-refresh.<your-cloudflare-subdomain>.workers.dev`

The URL itself is not secret. Only the Worker knows the token and passphrase.
A POST to `/refresh` without the password should return 401; requests from
other origins are rejected. Passwords are not accepted over plaintext HTTP.

## Step 3 — Configure the GitHub Pages link to Worker

Repository → **Settings → Secrets and variables → Actions → Variables** →
**New repository variable**:

- Name: `PUBGROUP_REFRESH_API_URL`
- Value: the **exact HTTPS Worker origin** returned by Wrangler; no `/refresh`
  suffix, no trailing path, no query string, no passwords or tokens.

The workflow creates `refresh-config.json` and updates the site's Content
Security Policy to allow HTTPS connections to this **one specific origin**.
Both are public (non-secret) configuration.

## Step 4 — Commit and publish

Upload the **complete modified source-only repository**, preserving the folder
structure. Make sure the updated `.github/workflows/main.yml`, `web/app.js`,
`web/index.html`, `pubgroup/export.py`, `web/refresh-config.json`, and
`refresh-backend/` are committed. Do not upload `web/publications.json`,
`data/`, `output/`, caches, token files, or plaintext generated PDFs.

Start **Actions → Monitor authors and deploy encrypted Pages → Run workflow**.
After its first successful **complete** run, the webpage will have its Worker
URL and a CSP `connect-src` entry. Reload the page to get the new JavaScript.

## Mandatory tests

1. `python3 -m unittest discover -s tests -v` → all Python tests pass.
2. `cd refresh-backend && npm test` → all backend tests pass.
3. First ensure a manual GitHub Actions collection/deployment succeeds. Hosted
   macOS TLS access to CiênciaVitae remains **unverified** until a live run.
4. Open the live website in a private browser window. Unlock with the saved
   passphrase. Click Refresh sources. Expect an accepted request, then an
   updated collection when a successful Pages deployment completes.
5. Click Refresh again immediately: expect HTTP 429 / a cooldown notice.
6. Try 8 incorrect authorizations from the same client/IP using a test client:
   the next attempt should be rejected for at most 10 minutes. Avoid hitting
   production limits while testing with real users.
7. Confirm a failed GitHub workflow **does not** result in a false success.
8. Inspect the Pages deployment artifact: only `index.html`, `app.js`,
   `styles.css`, `.nojekyll`, `manifest.json`, `bundle.enc.json`, and
   `refresh-config.json`. No plaintext JSON, bibliography or PDF.
9. Confirm neither secret exists in browser Network responses, repository
   files, or deployed website. The **password is intentionally transmitted**
   over HTTPS in the `POST /refresh` request; do not assume it never leaves the
   browser once Refresh is clicked.

## Security and operational limitations

- **One shared passphrase is shared authorization**, not per-person identity.
  Any user who has it can authorize a collection. It cannot selectively revoke
  one person. Rotate BOTH secrets and the encrypted bundle to revoke access.
- An authorized user may save decrypted publications/PDF; encryption does not
  prevent data exfiltration after authorized access.
- Cloudflare receives the refresh password over HTTPS and has to be trusted
  alongside GitHub. Never put a token in the public website.
- The request rate limit is durable because a SQLite-backed Durable Object
  serializes and persists state. It mitigates brute force and duplicate Actions
  runs; it cannot defend against all distributed denial-of-service attacks.
- `CF-Connecting-IP` is an edge-provided client address. The database stores
  HMAC identifiers, not raw IPs. Normal infrastructure logs can still contain
  IP addresses; configure account logging to match your privacy requirements.
- The global 15-minute cooldown is reserved BEFORE the GitHub API call. On
  an ambiguous network/API failure it stays in force to avoid duplicate runs.
- When 20 minutes elapse with no newer deployment, the browser reports that
  the request was accepted but not verified as complete; review GitHub Actions.
- GitHub Pages is public, including source and ciphertext. Keep the random
  passphrase long to resist offline guessing.
- GitHub Actions schedule executions are best effort; cache is not durable
  long-term archival storage; keep separate backup of encrypted state.
- Fine-grained PATs expire. Rotate `GITHUB_DISPATCH_TOKEN` in Cloudflare upon
  expiry without changing the library passphrase.

## Sources

- GitHub workflow dispatch: https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event
- Cloudflare Durable Objects: https://developers.cloudflare.com/durable-objects/get-started/
- Cloudflare SQLite storage: https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
- Cloudflare Worker secrets: https://developers.cloudflare.com/workers/configuration/secrets/
