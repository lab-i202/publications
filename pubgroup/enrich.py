"""Exact DOI cross-references. Title searches are suggestions, never imported."""
import re
from html import unescape
from difflib import SequenceMatcher
from urllib.parse import quote, urlencode
from .model import clean, norm, safe_url, valid_date
from .network import FetchError

def date_parts(value):
    try:
        return valid_date('-'.join(str(x) for x in value['date-parts'][0]))
    except (KeyError, TypeError, IndexError):
        return ''

def plain(s):
    return clean(unescape(re.sub(r'<[^>]+>', '', str(s or ''))))

def lookup(client, doi):
    try:
        m = client.json('https://api.crossref.org/works/' + quote(doi, safe=''))['message']
        title = plain((m.get('title') or [''])[0])
        d = next((v for field in ('published', 'published-online', 'published-print', 'issued')
                  if (v := date_parts(m.get(field, {})))), '')
        return dict(source='Crossref', title=title, date=d,
                    venue=plain((m.get('container-title') or [''])[0]), publisher=plain(m.get('publisher')),
                    authors=[clean(' '.join([a.get('given', ''), a.get('family', '')])) or a.get('name', '')
                             for a in m.get('author', [])], pages=clean(m.get('page')),
                    volume=clean(m.get('volume')), issue=clean(m.get('issue')),
                    url='https://doi.org/' + doi, type=m.get('type', ''), event=m.get('event', {}))
    except (FetchError, KeyError, ValueError):
        m = client.json('https://api.datacite.org/dois/' + quote(doi, safe=''))['data']['attributes']
        # DataCite publicationYear is reliable; other dates may be deposit/creation dates.
        dates = [valid_date(x.get('date')) for x in m.get('dates', []) if x.get('dateType') == 'Issued']
        d = next((x for x in dates if x), '') or valid_date(str(m.get('publicationYear', '')))
        return dict(source='DataCite', title=clean((m.get('titles') or [{}])[0].get('title')),
                    date=d, venue='', publisher=clean(m.get('publisher')),
                    authors=[clean(a.get('name')) for a in m.get('creators', [])],
                    url=safe_url(m.get('url')) or 'https://doi.org/' + doi,
                    type=(m.get('types') or {}).get('resourceTypeGeneral', ''))

def apply_metadata(p, m, basis):
    similarity = SequenceMatcher(None, norm(p['title']), norm(m['title'])).ratio()
    if similarity < .82:
        warning = 'DOI title differs from profile; metadata not applied'
        if warning not in p['warnings']:
            p['warnings'].append(warning)
        p['doi_check'] = dict(status='title conflict', **m)
        # Keep the supplied DOI as evidence, but do not present it as a verified
        # link to this paper or include it in the exported bibliographic DOI field.
        p['url'] = next((u for u in p.get('links', []) if 'doi.org/' not in u), '')
        return
    p['doi_check'] = dict(status='verified', **m)
    p['publisher_date'] = m.get('date', '')
    profile_date = p['date']
    if basis == 'publisher' and m.get('date'):
        p['date'], p['date_source'] = m['date'], m['source']
    elif m.get('date') and profile_date and m['date'][:4] == profile_date[:4] and len(m['date']) > len(profile_date):
        p['date'], p['date_source'] = m['date'], m['source'] + ' (profile year agrees)'
    if m.get('date') and p.get('profile_year') and m['date'][:4] != p['profile_year']:
        warning = 'Profile year ' + p['profile_year'] + ' differs from DOI year ' + m['date'][:4]
        if warning not in p['warnings']:
            p['warnings'].append(warning)
    for key in ('publisher', 'pages', 'volume', 'issue', 'venue'):
        if not p.get(key) and m.get(key):
            p[key] = m[key]
    # CV author attribution remains primary; missing author lists may be completed.
    if not p.get('authors') and m.get('authors'):
        p['authors'] = m['authors']
    link = safe_url(m.get('url'))
    if link and link not in p['links']:
        p['links'].append(link)

def enrich(items, client, basis='profile', title_candidates=False):
    audit, suggestions = [], []
    for index, p in enumerate(items, 1):
        if p.get('doi'):
            try:
                metadata = lookup(client, p['doi']); apply_metadata(p, metadata, basis)
                audit.append(dict(id=p['id'], doi=p['doi'], status=p['doi_check']['status'], source=metadata['source']))
            except (FetchError, KeyError, ValueError) as exc:
                audit.append(dict(id=p['id'], doi=p['doi'], status='unavailable', error=str(exc)))
        elif title_candidates:
            try:
                query = urlencode({'query.title': p['title'], 'rows': 3})
                candidates = client.json('https://api.crossref.org/works?' + query)['message']['items']
                for m in candidates:
                    title = clean((m.get('title') or [''])[0])
                    similarity = SequenceMatcher(None, norm(p['title']), norm(title)).ratio()
                    if similarity >= .8:
                        suggestions.append(dict(publication_id=p['id'], profile_title=p['title'],
                                                suggested_title=title, doi=m['DOI'],
                                                similarity=round(similarity, 3), requires_review=True))
            except (FetchError, KeyError, ValueError) as exc:
                audit.append(dict(id=p['id'], status='title search unavailable', error=str(exc)))
        if index % 25 == 0:
            print(f'  DOI check: {index}/{len(items)} records', flush=True)
    return audit, suggestions

def review_zotero(items, client, group_id):
    """Compare a public group library; unmatched items require human review.

    Bibliographic entries are not imported, because author attribution and group
    membership still need confirmation. Only top-level items are read.
    """
    import json
    from datetime import datetime, timezone
    from .model import doi_from
    group_id = str(group_id)
    if not group_id.isdigit():
        raise ValueError('zotero_group_id must be numeric')
    summary = dict(source='Zotero', group_id=group_id, status='ok', items=0, matched=0,
                   url='https://www.zotero.org/groups/' + group_id + '/library', review=[])
    start = 0
    try:
        while True:
            url = f'https://api.zotero.org/groups/{group_id}/items/top?format=json&limit=100&start={start}&v=3'
            body, info = client.get(url, 'application/json')
            batch = json.loads(body)
            if not isinstance(batch, list):
                raise ValueError('Unexpected Zotero response')
            summary['fetched_at'] = datetime.fromtimestamp(info['timestamp'], timezone.utc).isoformat(timespec='seconds')
            summary['cached'] = info['cached']
            for item in batch:
                data = item.get('data', {})
                if data.get('itemType') in ('attachment', 'note') or not data.get('title'):
                    continue
                title, doi = clean(data['title']), doi_from(data.get('DOI'))
                summary['items'] += 1
                matched = next((p for p in items if norm(p['title']) == norm(title)
                                or (doi and p.get('doi') == doi and SequenceMatcher(None,norm(p['title']),norm(title)).ratio() >= .90)), None)
                if matched:
                    summary['matched'] += 1
                else:
                    summary['review'].append(dict(title=title, doi=doi, date=clean(data.get('date')),
                        type=data.get('itemType', ''), url=safe_url(data.get('url')),
                        source_url=safe_url(item.get('links', {}).get('alternate', {}).get('href')),
                        authors=[clean(' '.join([c.get('firstName',''),c.get('lastName','')])) or clean(c.get('name'))
                                 for c in data.get('creators', [])], requires_review=True))
            if len(batch) < 100:
                break
            start += len(batch)
    except (FetchError, ValueError, KeyError) as exc:
        summary['status'], summary['error'] = 'unavailable', str(exc)
    return summary
