"""Normalization, conservative deduplication, chronology and BibTeX."""
import copy
import hashlib
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from datetime import date
from urllib.parse import unquote, urlsplit

TYPES = {
    'conference': 'Conference paper', 'journal': 'Journal article',
    'chapter': 'Book chapter', 'book': 'Book', 'poster': 'Conference poster',
    'abstract': 'Conference abstract', 'thesis': 'Thesis', 'preprint': 'Preprint',
    'report': 'Report', 'other': 'Other publication',
}

def clean(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()

def norm(s):
    s = unicodedata.normalize('NFKD', clean(s).casefold())
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in s if not unicodedata.combining(c)))

def doi_from(s):
    m = re.search(r'10\.\d{4,9}/[^\s<>"]+', unquote(str(s or '')), re.I)
    return m.group(0).rstrip('.,;').lower() if m else ''

def safe_url(s):
    s = clean(s)
    p = urlsplit(s)
    return s if p.scheme in ('http', 'https') and p.netloc and not p.username and not p.password else ''

def valid_date(s):
    try:
        parts = [int(x) for x in str(s).split('-')]
        if len(parts) not in (1, 2, 3):
            return ''
        date(parts[0], parts[1] if len(parts) > 1 else 1, parts[2] if len(parts) > 2 else 1)
        if not 1500 <= parts[0] <= 2200:
            return ''
        return '-'.join([f'{parts[0]:04}'] + [f'{p:02}' for p in parts[1:]])
    except (ValueError, TypeError):
        return ''

def sort_key(p):
    parts = (p.get('activity_date') or p.get('date') or '').split('-')
    # Unknown month/day sorts AFTER known dates in that year, not an invented December.
    return tuple(int(x) if x.isdigit() else 0 for x in (parts + ['0', '0'])[:3])

def identity(p):
    basis = 'doi:' + p['doi'] + '|' + norm(p['title']) if p.get('doi') else '|'.join([
        norm(p['title']), str(p.get('profile_year') or p.get('date', '')[:4]), p['type']])
    return hashlib.sha256(basis.encode()).hexdigest()[:20]

def equivalent(a, b):
    if a.get('doi') and b.get('doi'):
        # CVs sometimes assign a whole book-of-abstracts DOI to several different
        # abstracts, or contain an incorrect DOI. A shared DOI alone is insufficient.
        return (a['doi'] == b['doi'] and SequenceMatcher(None, norm(a['title']), norm(b['title'])).ratio() >= .90)
    return (norm(a['title']) == norm(b['title'])
            and (a.get('profile_year') or a.get('date', '')[:4]) == (b.get('profile_year') or b.get('date', '')[:4])
            and a['type'] == b['type'])

def merge(a, b):
    """Same DOI or exact normalized title/year/type. Never fuzzy-merge editions."""
    out = copy.deepcopy(a)
    if a['type'] != b['type']:
        out.setdefault('warnings', []).append('Profiles classify this record differently: ' + a['type'] + ' / ' + b['type'])
    for field in ['doi', 'venue', 'publisher', 'pages', 'volume', 'issue', 'url', 'status']:
        if not out.get(field) or (field == 'status' and out.get(field) == 'unspecified'):
            out[field] = b.get(field, '')
    if len(b.get('authors', [])) > len(out.get('authors', [])):
        out['authors'] = b['authors']
    out['researcher_ids'] = sorted(set(a.get('researcher_ids', []) + b.get('researcher_ids', [])))
    for src in b.get('sources', []):
        if src not in out['sources']:
            out['sources'].append(src)
    for field in ['warnings', 'links']:
        out[field] = list(dict.fromkeys(out.get(field, []) + b.get(field, [])))
    if a.get('date') and b.get('date') and a['date'][:4] != b['date'][:4]:
        warning = 'Profile years disagree: ' + a['date'][:4] + ' / ' + b['date'][:4]
        if warning not in out['warnings']:
            out['warnings'].append(warning)
    return out

def deduplicate(items):
    out = []
    for p in items:
        found = next((i for i, q in enumerate(out) if equivalent(p, q)), None)
        if found is None:
            out.append(copy.deepcopy(p))
        else:
            out[found] = merge(out[found], p)
    for p in out:
        p['id'] = identity(p)
    return sorted(out, key=lambda p: (sort_key(p), p['title'].casefold()), reverse=True)

def select(items, report, year):
    period = str(report.get('period', 'current'))
    if period == 'current':
        lo = hi = year
    elif period == 'all':
        lo, hi = 1500, 2200
    elif period == 'range':
        lo, hi = int(report['start_year']), int(report['end_year'])
        if lo > hi:
            raise ValueError('start_year must not exceed end_year')
    else:
        lo = hi = int(period)
    types, statuses = report.get('include_types', []), report.get('include_statuses', [])
    result = [p for p in items if (p.get('date') and lo <= int(p['date'][:4]) <= hi)
              or (not p.get('date') and period == 'all')]
    result = [p for p in result if (not types or p['type'] in types)
              and (not statuses or p['status'] in statuses)]
    return sorted(result, key=lambda p: (sort_key(p), p['title'].casefold()), reverse=True)

def metrics(items):
    monthly, publication_months, conference_months = Counter(), Counter(), Counter()
    for p in items:
        dt = p.get('activity_date') or p.get('date', '')
        if len(dt) >= 7:
            monthly[dt[:7]] += 1
            target = conference_months if p.get('activity_date_source') == 'conference' else publication_months
            target[dt[:7]] += 1
    return {
        'total': len(items), 'types': dict(Counter(p['type'] for p in items)),
        'statuses': dict(Counter(p['status'] for p in items)), 'months': dict(sorted(monthly.items())),
        'publication_months': dict(sorted(publication_months.items())),
        'conference_months': dict(sorted(conference_months.items())),
        'unknown_month': sum(len(p.get('activity_date') or p.get('date', '')) < 7 for p in items),
        'with_doi': sum(bool(p.get('doi')) for p in items),
        'researcher_count': len({r for p in items for r in p['researcher_ids']}),
        'conference_records': sum(p['type'] in ('conference', 'poster', 'abstract') for p in items),
        'conference_venues': len({p.get('event', {}).get('id') or norm(p.get('venue')) for p in items
                                  if p['type'] in ('conference', 'poster', 'abstract') and p.get('venue')}),
    }

def tex_escape(s):
    mapping = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$',
               '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}',
               '^': r'\textasciicircum{}'}
    return ''.join(mapping.get(c, c) for c in str(s or '') if c >= ' ' or c == '\n')

def bibtex(p):
    kind = {'journal': 'article', 'conference': 'inproceedings', 'chapter': 'incollection',
            'book': 'book', 'thesis': 'phdthesis'}.get(p['type'], 'misc')
    # A master's thesis must never be described as a PhD thesis.
    if p['type'] == 'thesis' and re.search(r'mestrado|master', p.get('raw', ''), re.I):
        kind = 'mastersthesis'
    key = 'pub' + p['id']
    conflict = p.get('doi_check', {}).get('status') == 'title conflict'
    fields = {'title': '{' + tex_escape(p['title']) + '}',
              'author': ' and '.join(tex_escape(a) for a in p.get('authors', [])),
              'year': p.get('date', '')[:4], 'doi': '' if conflict else tex_escape(p.get('doi', '')),
              'url': tex_escape(p.get('url', ''))}
    if p.get('venue'):
        field = 'journal' if kind == 'article' else 'booktitle' if kind in ('inproceedings', 'incollection') else 'howpublished'
        fields[field] = tex_escape(p['venue'])
    for field in ['publisher', 'volume', 'pages']:
        if p.get(field):
            fields[field] = tex_escape(p[field])
    if p.get('issue'):
        fields['number'] = tex_escape(p['issue'])
    if p['type'] in ('poster', 'abstract'):
        fields['note'] = TYPES[p['type']]
    if p.get('status') in ('accepted', 'in press'):
        fields['note'] = (fields.get('note', '') + '; ' + p['status']).strip('; ')
    if conflict:
        fields['note'] = (fields.get('note', '') + '; Source DOI omitted because its title differs').strip('; ')
    return '@' + kind + '{' + key + ',\n' + ',\n'.join('  ' + k + ' = {' + v + '}' for k, v in fields.items() if v) + '\n}\n'
