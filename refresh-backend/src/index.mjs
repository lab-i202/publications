/**
 * Secure public-site refresh endpoint.
 * Secrets live only in Cloudflare Workers, never in GitHub Pages or Git history.
 * One SQLite-backed Durable Object provides a serialized, durable global cooldown
 * and per-IP authentication attempt limit.
 */
import { DurableObject } from 'cloudflare:workers';
import {COOLDOWN_MS, MAX_PASSWORD_LENGTH, nextAttempt, cooldownStatus,
        validatePassphrase, sanitizedGithubError} from './logic.mjs';

const encoder = new TextEncoder();
const JSON_HEADERS = {'Content-Type':'application/json; charset=utf-8', 'Cache-Control':'no-store',
                      'X-Content-Type-Options':'nosniff'};

function json(result, status = 200, extra = {}) {
  return new Response(JSON.stringify(result), {status, headers: {...JSON_HEADERS, ...extra}});
}
function corsHeaders(origin) {
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '600',
    'Vary': 'Origin',
  };
}
async function sha256(data) { return new Uint8Array(await crypto.subtle.digest('SHA-256', encoder.encode(data))); }
async function samePassphrase(candidate, expected) {
  // Compare equal-length hashes without short-circuiting. No secret leaves the Worker.
  const a = await sha256(candidate);
  const b = await sha256(expected);
  let mismatch = 0;
  for (let i = 0; i < a.length; ++i) mismatch |= a[i] ^ b[i];
  return mismatch === 0;
}
async function anonymizedIp(ip, secret) {
  const key = await crypto.subtle.importKey('raw', encoder.encode(secret),
    {name:'HMAC', hash:'SHA-256'}, false, ['sign']);
  const digest = await crypto.subtle.sign('HMAC', key, encoder.encode('pubgroup-ip:v1:' + ip));
  return [...new Uint8Array(digest)].map(x => x.toString(16).padStart(2, '0')).join('');
}

export class RefreshCoordinator extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.sql = ctx.storage.sql;
    this.sql.exec('CREATE TABLE IF NOT EXISTS attempts (ip_hash TEXT PRIMARY KEY, start_ms INTEGER NOT NULL, count INTEGER NOT NULL)');
    this.sql.exec('CREATE TABLE IF NOT EXISTS global_state (id INTEGER PRIMARY KEY CHECK(id=1), last_dispatch_ms INTEGER NOT NULL)');
    // Prevent interleaving requests while dispatching GitHub Actions. Durable state
    // persists across restarts/evictions of this singleton object.
    this.queue = Promise.resolve();
  }

  async requestRefresh(passphrase, ip) {
    let release;
    const next = new Promise(resolve => {release = resolve;});
    const previous = this.queue;
    this.queue = next;
    await previous;
    try {
      return await this.handleRequest(passphrase, ip);
    } finally {
      release();
    }
  }

  async handleRequest(passphrase, ip) {
    const now = Date.now();
    if (!this.env.REFRESH_PASSPHRASE || this.env.REFRESH_PASSPHRASE.length < 14 ||
        !this.env.GITHUB_DISPATCH_TOKEN) {
      return {status: 503, body: {error:'The refresh service is not configured.'}};
    }
    // Keep the table bounded without accumulating raw IPs or credentials.
    this.sql.exec('DELETE FROM attempts WHERE start_ms < ?', now - 10*60*1000);
    const ipHash = await anonymizedIp(ip || 'unknown', this.env.REFRESH_PASSPHRASE);
    const row = this.sql.exec('SELECT start_ms, count FROM attempts WHERE ip_hash=?', ipHash).toArray()[0];
    const attempt = nextAttempt(row && {start: row.start_ms, count: row.count}, now);
    this.sql.exec('INSERT INTO attempts(ip_hash,start_ms,count) VALUES(?,?,?) ON CONFLICT(ip_hash) DO UPDATE SET start_ms=excluded.start_ms, count=excluded.count',
      ipHash, attempt.start, attempt.count);
    if (!attempt.allowed) return {status:429, body:{error:'Too many attempts from this connection.', retry_after:attempt.retryAfter}};
    if (!validatePassphrase(passphrase) || !await samePassphrase(passphrase, this.env.REFRESH_PASSPHRASE)) {
      return {status:401, body:{error:'Refresh authorization failed.'}};
    }
    const global = this.sql.exec('SELECT last_dispatch_ms FROM global_state WHERE id=1').toArray()[0];
    const cooldown = cooldownStatus(global?.last_dispatch_ms, now);
    if (!cooldown.allowed) return {status:429, body:{error:'A refresh was recently requested. Please wait.', retry_after:cooldown.retryAfter}};

    // Reserve the cooldown before making the external request so no parallel
    // requests can dispatch duplicates. In an ambiguous network failure we
    // deliberately keep the cooldown (fail closed).
    this.sql.exec('INSERT INTO global_state(id,last_dispatch_ms) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET last_dispatch_ms=excluded.last_dispatch_ms', now);
    const owner = this.env.GITHUB_OWNER;
    const repo = this.env.GITHUB_REPO;
    const workflow = this.env.GITHUB_WORKFLOW;
    const ref = this.env.GITHUB_REF;
    if (![owner,repo,workflow,ref].every(x => typeof x === 'string' && /^[a-zA-Z0-9_.-]+$/.test(x))) {
      return {status:503, body:{error:'GitHub dispatch settings are invalid.'}};
    }
    try {
      const github = await fetch(`https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflow}/dispatches`, {
        method:'POST',
        headers: {
          'Authorization':`Bearer ${this.env.GITHUB_DISPATCH_TOKEN}`,
          'Accept':'application/vnd.github+json',
          'X-GitHub-Api-Version':'2026-03-10',
          'User-Agent':'PublicationGroup-Refresh/1.0',
          'Content-Type':'application/json',
        },
        body:JSON.stringify({ref,inputs:{period:'current',fresh:'true',reset_state:'false'}}),
      });
      if (github.status !== 200 && github.status !== 204) return {status:502, body:{error:sanitizedGithubError(github.status)}};
      return {status:202, body:{accepted:true, message:'Publication collection was requested. The website will update after deployment.', cooldown_seconds:Math.floor(COOLDOWN_MS/1000)}};
    } catch {
      return {status:502, body:{error:'Unable to contact GitHub. Check backend connectivity and try again after the cooldown.'}};
    }
  }
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin');
    const allowedOrigin = env.ALLOWED_ORIGIN;
    if (!allowedOrigin || origin !== allowedOrigin) return json({error:'Origin not permitted.'}, 403);
    const headers = corsHeaders(origin);
    const pathname = new URL(request.url).pathname;
    if (pathname !== '/refresh') return json({error:'Not found.'}, 404, headers);
    if (request.method === 'OPTIONS') return new Response(null, {status:204, headers:{...headers, 'Cache-Control':'no-store'}});
    if (request.method !== 'POST') return json({error:'Method not allowed.'}, 405, headers);
    if (request.headers.get('Content-Type')?.split(';')[0].trim().toLowerCase() !== 'application/json')
      return json({error:'Only application/json is accepted.'}, 415, headers);
    const claimedSize = Number(request.headers.get('Content-Length') || 0);
    if (claimedSize > 1200) return json({error:'Request is too large.'}, 413, headers);
    let data;
    try {
      const body = await request.text();
      if (body.length > 1200) return json({error:'Request is too large.'}, 413, headers);
      data = JSON.parse(body);
      if (!data || typeof data !== 'object' || Array.isArray(data) || !validatePassphrase(data.passphrase) || Object.keys(data).length !== 1) {
        // Malformed passwords still count toward the rate limit.
        data = {passphrase:''};
      }
    } catch { data = {passphrase:''}; }
    try {
      const stub = env.REFRESH_COORDINATOR.getByName('publications');
      const result = await stub.requestRefresh(data.passphrase, request.headers.get('CF-Connecting-IP') || 'unknown');
      return json(result.body, result.status, {...headers, ...(result.body?.retry_after ? {'Retry-After':String(result.body.retry_after)} : {})});
    } catch {
      return json({error:'Refresh service unavailable. Please try again later.'}, 503, headers);
    }
  },
};
