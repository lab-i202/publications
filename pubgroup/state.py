"""Persistent changes. First run establishes a baseline; DOI upgrades retain IDs."""
import copy
import hashlib
import json
import os
from pathlib import Path
from .model import equivalent, identity

def atomic_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)

def fingerprint(p):
    meaningful = {k: p.get(k) for k in ('title', 'authors', 'date', 'doi', 'venue', 'type', 'status',
                                        'researcher_ids', 'links', 'publisher', 'pages', 'volume', 'issue')}
    meaningful['citations'] = sorted(s['citation'] for s in p.get('sources', []))
    return hashlib.sha256(json.dumps(meaningful, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def reconcile(current, previous, at):
    old = previous.get('publications', []) if previous else []
    baseline = not previous
    changes = dict(baseline=baseline, new=[], updated=[], no_longer_listed=[])
    for p in current:
        prior = next((q for q in old if q['id'] == p['id'] or equivalent(p, q)), None)
        if prior:
            p['id'] = prior['id']
            p['first_seen'] = prior.get('first_seen', at)
            p['is_new'] = False
            if fingerprint(p) != fingerprint(prior):
                changes['updated'].append(p['id']); p['last_changed'] = at
            else:
                p['last_changed'] = prior.get('last_changed', at)
        else:
            p['id'] = identity(p); p['first_seen'] = at; p['last_changed'] = at
            p['is_new'] = not baseline
            if not baseline:
                changes['new'].append(p['id'])
    ids = {p['id'] for p in current}
    changes['no_longer_listed'] = [p['id'] for p in old if p['id'] not in ids]
    return changes
