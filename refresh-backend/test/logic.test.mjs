import test from 'node:test';
import assert from 'node:assert/strict';
import {MAX_ATTEMPTS_PER_IP, WINDOW_MS, COOLDOWN_MS, nextAttempt,
        cooldownStatus, validatePassphrase, validateApiUrl, sanitizedGithubError} from '../src/logic.mjs';

test('validates passphrase type, length and limits', () => {
  assert.equal(validatePassphrase('a'.repeat(64)),true);
  assert.equal(validatePassphrase('tiny'),false);
  assert.equal(validatePassphrase(123),false);
  assert.equal(validatePassphrase('a'.repeat(513)),false);
});
test('per-IP limiter permits exactly N attempts in window', () => {
  let state=null;
  for (let i=0;i<MAX_ATTEMPTS_PER_IP;i++) {
    state=nextAttempt(state,1000);
    assert.equal(state.allowed,true);
  }
  state=nextAttempt(state,1001);
  assert.equal(state.allowed,false);
  assert.ok(state.retryAfter>0);
  assert.equal(nextAttempt(state,1000+WINDOW_MS).allowed,true);
});
test('global cooldown guarantees at most one request per interval', () => {
  assert.equal(cooldownStatus(null,1000).allowed,true);
  assert.equal(cooldownStatus(1000,1001).allowed,false);
  assert.equal(cooldownStatus(1000,1000+COOLDOWN_MS).allowed,true);
});
test('only strict HTTPS root endpoints are accepted', () => {
  assert.equal(validateApiUrl('https://refresh.example.workers.dev'), 'https://refresh.example.workers.dev');
  for (const v of ['http://example.com','https://foo.com/path','https://user:pass@foo.com','https://foo.com/?x=1','',null])
    assert.equal(validateApiUrl(v),null);
});
test('GitHub errors never include response bodies or token data', () => {
  assert.match(sanitizedGithubError(403), /token/);
  assert.match(sanitizedGithubError(422), /workflow/);
});
