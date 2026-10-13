import test from 'node:test';
import assert from 'node:assert/strict';
import worker, {RefreshCoordinator} from '../src/index.mjs';

class FakeSQL {
  constructor() { this.attempts = new Map(); this.lastDispatch = null; }
  exec(query, ...args) {
    const sql = query.trim();
    let rows = [];
    if (sql.startsWith('DELETE FROM attempts')) {
      for (const [key, val] of this.attempts) if (val.start_ms < args[0]) this.attempts.delete(key);
    } else if (sql.startsWith('SELECT start_ms, count')) {
      const row = this.attempts.get(args[0]); if (row) rows=[row];
    } else if (sql.startsWith('INSERT INTO attempts')) {
      this.attempts.set(args[0], {start_ms:args[1],count:args[2]});
    } else if (sql.startsWith('SELECT last_dispatch_ms')) {
      if (this.lastDispatch !== null) rows=[{last_dispatch_ms:this.lastDispatch}];
    } else if (sql.startsWith('INSERT INTO global_state')) {
      this.lastDispatch = args[0];
    } else if (!sql.startsWith('CREATE TABLE')) {
      throw Error('Unknown SQL call: ' + sql);
    }
    return {toArray: () => rows};
  }
}

const pass = 'h'.repeat(64);
function setup() {
  const env = {
    REFRESH_PASSPHRASE:pass,
    GITHUB_DISPATCH_TOKEN:'private-token-do-not-expose',
    GITHUB_OWNER:'lab-i202', GITHUB_REPO:'publications', GITHUB_WORKFLOW:'main.yml', GITHUB_REF:'main',
    ALLOWED_ORIGIN:'https://lab-i202.github.io',
  };
  const coordinator = new RefreshCoordinator({storage:{sql:new FakeSQL()}},env);
  env.REFRESH_COORDINATOR = {getByName(name) {assert.equal(name,'publications');return coordinator;}};
  const request = (password, origin=env.ALLOWED_ORIGIN) => new Request('https://worker.example.dev/refresh', {
    method:'POST', headers:{Origin:origin, 'Content-Type':'application/json', 'CF-Connecting-IP':'192.0.2.1'},
    body:JSON.stringify({passphrase:password}),
  });
  return {env,coordinator,request};
}

test('wrong password is refused, a valid one dispatches, second is globally limited', async () => {
  const {env,request} = setup();
  const realFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, params) => {
    calls.push({url, params});
    return new Response(JSON.stringify({workflow_run_id: 123, html_url:"https://github.com/example/run/123"}), {status:200});
  };
  try {
    const bad = await worker.fetch(request('x'.repeat(64)),env);
    assert.equal(bad.status,401);
    assert.equal(calls.length,0);
    const success = await worker.fetch(request(pass),env);
    assert.equal(success.status,202);
    assert.equal((await success.json()).accepted,true);
    assert.equal(calls.length,1);
    assert.match(calls[0].url,/lab-i202\/publications\/actions\/workflows\/main.yml\/dispatches/);
    assert.deepEqual(JSON.parse(calls[0].params.body).inputs,{period:'current',fresh:'true',reset_state:'false'});
    assert.ok(!calls[0].params.body.includes(pass));
    const repeat = await worker.fetch(request(pass),env);
    assert.equal(repeat.status,429);
    assert.equal(calls.length,1);
  } finally { globalThis.fetch = realFetch; }
});

test('serialized parallel requests dispatch only once', async () => {
  const {env,request} = setup();
  const realFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {calls++; await new Promise(r=>setTimeout(r,20));return new Response(null,{status:204});};
  try {
    const replies=await Promise.all([worker.fetch(request(pass),env),worker.fetch(request(pass),env)]);
    assert.deepEqual(replies.map(x=>x.status).sort(),[202,429]);
    assert.equal(calls,1);
  } finally {globalThis.fetch = realFetch;}
});

test('untrusted origin cannot trigger dispatch and CORS is strict', async () => {
  const {env,request} = setup();
  const bad = await worker.fetch(request(pass,'https://attacker.example'),env);
  assert.equal(bad.status,403);
  assert.equal(bad.headers.get('Access-Control-Allow-Origin'),null);
  const preflight = await worker.fetch(new Request('https://worker.example.dev/refresh',{
    method:'OPTIONS',headers:{Origin:'https://lab-i202.github.io'}}),env);
  assert.equal(preflight.status,204);
  assert.equal(preflight.headers.get('Access-Control-Allow-Origin'),env.ALLOWED_ORIGIN);
});

test('bounded failed attempts deny further guessing',async () => {
  const {env,request} = setup();
  for(let i=0;i<8;i++) assert.equal((await worker.fetch(request('z'.repeat(64)),env)).status,401);
  const blocked = await worker.fetch(request(pass),env);
  assert.equal(blocked.status,429);
  assert.ok(Number(blocked.headers.get('Retry-After')) > 0);
});
