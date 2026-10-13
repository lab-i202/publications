"""Collect all sources, preserve failed-source records, build outputs and save state."""
import copy
import json
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from . import __version__, BUILD
from .enrich import enrich, review_zotero
from .events import annotate, conferences, display_name, resolve_events
from .export import build_web
from .model import bibtex, deduplicate, metrics, select, TYPES, norm
from .network import Client, FetchError
from .parser import parse_profile
from .report import write_report
from .state import atomic_json, reconcile

def load_config(path):
    path = Path(path).resolve()
    with path.open('rb') as f:
        cfg = tomllib.load(f)
    profiles = cfg.get('researchers', [])
    if not profiles or len({p['id'] for p in profiles}) != len(profiles):
        raise ValueError('Configure at least one researcher, with unique IDs')
    for p in profiles:
        expected = 'https://www.cienciavitae.pt/portal/' + p['id']
        if p['url'] != expected:
            raise ValueError('Use the canonical public CiênciaVitae portal URL for ' + p['id'])
    report = cfg.setdefault('report', {})
    if report.get('date_basis', 'profile') not in ('profile', 'publisher'):
        raise ValueError('date_basis must be profile or publisher')
    if any(t not in TYPES for t in report.get('include_types', [])):
        raise ValueError('Unknown include_types value')
    statuses = {'published', 'accepted', 'in press', 'unspecified'}
    if any(t not in statuses for t in report.get('include_statuses', [])):
        raise ValueError('Unknown include_statuses value')
    return cfg, path.parent

def make_dataset(items, researchers, sources, changes, cfg, at, year, audit=None, candidates=None):
    report = cfg['report']
    annotate(items, cfg.get('_calendar', {}))
    researchers = [dict(r, name=display_name(r['name'])) for r in researchers]
    researchers.sort(key=lambda r: norm(r['name']))
    selected = select(items, report, year)
    for p in items:
        p['bibtex'] = bibtex(p)
    period = str(report.get('period', 'current'))
    label = str(year) if period == 'current' else 'All years' if period == 'all' else str(report['start_year']) + '-' + str(report['end_year']) if period == 'range' else period
    return dict(schema_version=1, version=__version__, build=BUILD, group=cfg['group']['name'],
                timezone=cfg['group'].get('timezone', 'Europe/Lisbon'), generated_at=at,
                current_year=year, period_label=label, date_basis=report.get('date_basis', 'profile'),
                publications=selected, catalogue=items, total_catalogue=len(items), researchers=researchers,
                sources=sources, changes=changes, metrics=metrics(selected), conferences=conferences(selected),
                calendar_sources=[dict(name=e['name'], url=e['source_url']) for e in {e['id']:e for e in cfg.get('_calendar', {}).values() if e.get('status') == 'resolved'}.values()],
                enrichment_audit=audit or [], candidates=candidates or [],
                reference_urls=cfg['group'].get('reference_urls', []))

def _run(config_path, period=None, offline=False, refresh=False, no_pdf=False, no_enrich=False,
        passphrase=None, report_only=False):
    cfg, root = load_config(config_path)
    if period is not None:
        cfg['report']['period'] = period
    now = datetime.now(ZoneInfo(cfg['group'].get('timezone', 'Europe/Lisbon')))
    at, year = now.isoformat(timespec='seconds'), now.year
    # Validate period before making network requests or changing files.
    select([], cfg['report'], year)
    state_path = root / 'data' / 'state.json'
    previous = json.loads(state_path.read_text()) if state_path.exists() else None
    client = Client(root / 'cache' / 'http', cfg['network'], offline, refresh)
    researchers, sources, all_items, rejected = [], [], [], []
    if report_only:
        if not previous:
            raise ValueError('No saved collection. Run the collector first.')
        all_items = copy.deepcopy(previous['publications'])
        researchers, sources = previous['researchers'], previous['sources']
        changes = previous['changes']
        audit, candidates = previous.get('enrichment_audit', []), previous.get('candidates', [])
        reference_audit = previous.get('reference_audit', {})
    else:
        old_by_id = {r['id']: r for r in previous.get('researchers', [])} if previous else {}
        for profile in cfg['researchers']:
            print('Reading ' + profile['id'] + ' …', flush=True)
            s = dict(researcher_id=profile['id'], url=profile['url'], status='ok', checked_at=at)
            try:
                client.allowed(profile['url'])
                html, info = client.get(profile['url'])
                fetched_at = datetime.fromtimestamp(info['timestamp'], timezone.utc).isoformat(timespec='seconds')
                r, pubs, warnings, rejects = parse_profile(html, profile, fetched_at)
                if rejects:
                    # A partial parser result must not remove previously readable records.
                    s['status'] = 'partial'
                    s['error'] = 'Some citations could not be parsed; prior source records retained'
                s.update(record_count=len(pubs), rejected_count=len(rejects), cached=info['cached'],
                         fetched_at=fetched_at, warnings=warnings)
                all_items.extend(pubs); researchers.append(r)
                rejected.extend(dict(researcher_id=profile['id'], **x) for x in rejects)
            except (FetchError, ValueError) as exc:
                s.update(status='unavailable', error=str(exc), record_count=0, rejected_count=0)
                researchers.append(old_by_id.get(profile['id'], dict(id=profile['id'], name=profile['id'], url=profile['url'], orcid='')))
            if s['status'] != 'ok' and previous:
                for old in previous['publications']:
                    source_records = [src for src in old['sources'] if src['researcher_id'] == profile['id']]
                    if source_records:
                        p = copy.deepcopy(old); p['sources'] = source_records; p['researcher_ids'] = [profile['id']]
                        all_items.append(p)
            sources.append(s)
        if not all_items and not any(s['status'] == 'ok' for s in sources):
            raise RuntimeError('No publication records could be read. Previous outputs and baseline were preserved.')
        all_items = deduplicate(all_items)
        # Retain DOI enrichment across runs. Do not revert dates and metadata just
        # because an API is temporarily unavailable or --no-enrich is used.
        if previous:
            from .model import equivalent
            from .enrich import apply_metadata
            for p in all_items:
                prior = next((q for q in previous['publications'] if equivalent(p, q)), None)
                if prior and prior.get('doi_check', {}).get('status') == 'verified' and prior.get('doi') == p.get('doi'):
                    apply_metadata(p, {k: v for k, v in prior['doi_check'].items() if k != 'status'}, cfg['report'].get('date_basis', 'profile'))
        audit, candidates = [], []
        if cfg.get('enrichment', {}).get('enabled', True) and not no_enrich:
            # Enrich all by default: publisher dates can move records between years.
            # Cached exact-DOI queries make subsequent runs inexpensive.
            audit, candidates = enrich(all_items, client, cfg['report'].get('date_basis', 'profile'),
                                       cfg['enrichment'].get('title_candidates', False))
        reference_audit = {}
        if cfg.get('enrichment', {}).get('review_zotero') and not no_enrich:
            reference_audit = review_zotero(all_items, client, cfg['enrichment']['zotero_group_id'])
        changes = reconcile(all_items, previous, at)
    event_items = all_items if cfg.get('events', {}).get('scope') == 'all' else select(all_items, cfg['report'], year)
    cfg['_calendar'] = resolve_events(event_items, client, root / 'data' / 'conference_dates.json',
                                       cfg.get('events', {}), report_only=report_only, researchers=researchers)
    dataset = make_dataset(all_items, researchers, sources, changes, cfg, at, year, audit, candidates)
    dataset['reference_audit'] = reference_audit
    output = root / cfg['output'].get('directory', 'output')
    # Save collection BEFORE a possible TeX failure. A successful fetch should not
    # be lost; report can be rerun without network, and changes remain reviewable.
    if not report_only:
        if previous:
            atomic_json(root / 'data' / 'previous-state.json', previous)
        atomic_json(state_path, dict(publications=all_items, researchers=researchers, sources=sources,
                                    changes=changes, collected_at=at, enrichment_audit=audit, candidates=candidates, reference_audit=reference_audit))
        atomic_json(output / 'audit' / 'rejected.json', rejected)
    atomic_json(output / 'audit' / 'sources.json', sources)
    atomic_json(output / 'audit' / 'doi-checks.json', audit)
    atomic_json(output / 'audit' / 'candidates.json', candidates)
    atomic_json(output / 'audit' / 'zotero-review.json', reference_audit)
    atomic_json(output / 'audit' / 'changes.json', changes)
    atomic_json(output / 'audit' / 'conference-dates.json', cfg['_calendar'])
    atomic_json(output / 'publications.json', dataset)
    (output / 'publications.bib').write_text('\n'.join(bibtex(p) for p in dataset['publications']), encoding='utf-8')
    tex, pdf = write_report(dataset, output / 'pdf', not no_pdf and cfg['output'].get('compile_pdf', True))
    destination = root / cfg['output'].get('web_directory', 'web')
    build_web(dataset, pdf, destination, passphrase)
    print(f"\n{len(all_items)} unique catalogue records; {len(dataset['publications'])} in {dataset['period_label']}.")
    print(f"Changes: baseline={changes['baseline']}, new={len(changes['new'])}, updated={len(changes['updated'])}.")
    print(f"PDF: {pdf or 'not compiled; source at ' + str(tex)}\nWebsite: {destination}")
    return dataset


def run(config_path, **kwargs):
    """Serialize state and output writes across all entry points."""
    from .locking import OperationLock
    _, root = load_config(config_path)
    with OperationLock(root / "data" / "collector.lock"):
        return _run(config_path, **kwargs)
