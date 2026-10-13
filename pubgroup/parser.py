"""Parse ONLY the Publicações/Outputs publication table from public CV HTML.

The small DOM parser avoids executing profile JavaScript or collecting contact details.
Unknown sections and unparseable citations are recorded, never silently counted.
"""
import re
from html.parser import HTMLParser
from .model import clean, doi_from, norm, safe_url, valid_date

class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []
    def nodes(self, tag=None):
        for c in self.children:
            if isinstance(c, Node):
                if tag is None or c.tag == tag:
                    yield c
                yield from c.nodes(tag)
    def text(self, omit=()):
        if self.tag in omit:
            return ''
        return ''.join(c.text(omit) if isinstance(c, Node) else c for c in self.children)

class DOM(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node('root'); self.current = self.root; self.feed(html)
    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.current); self.current.children.append(n)
        if tag not in self.VOID:
            self.current = n
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)
    def handle_endtag(self, tag):
        n = self.current
        while n.parent:
            if n.tag == tag:
                self.current = n.parent; break
            n = n.parent
    def handle_data(self, data):
        self.current.children.append(data)

CATEGORY = {
    'artigoemconferencia': 'conference', 'conferencepaper': 'conference',
    'artigoemrevista': 'journal', 'journalarticle': 'journal',
    'capitulodelivro': 'chapter', 'bookchapter': 'chapter',
    'livro': 'book', 'book': 'book', 'livroeditado': 'book', 'editedbook': 'book',
    'posteremconferencia': 'poster', 'conferenceposter': 'poster',
    'resumoemconferencia': 'abstract', 'conferenceabstract': 'abstract',
    'tesedissertacao': 'thesis', 'dissertation': 'thesis', 'thesisdissertation': 'thesis',
    'preimpressao': 'preprint', 'preprint': 'preprint', 'relatorio': 'report', 'report': 'report',
}

def parse_citation(li, category, researcher, source, fetched_at):
    text = clean(li.text(omit=('div', 'script', 'style')))
    raw = clean(li.text())
    # The source uses double quotes around titles. Fall back to curly quotes.
    match = re.search(r'["“](.+?)["”]', text)
    if match:
        title = clean(match.group(1))
        before, after = text[:match.start()], text[match.end():]
    else:
        italic = next(iter(li.nodes('i')), None)
        if italic is None or not clean(italic.text()):
            raise ValueError('No quoted or italic title: ' + text[:100])
        title = clean(italic.text())
        pos = text.find(title)
        before, after = text[:pos], text[pos + len(title):]
        # Reports place the year before their title.
        report_year = re.search(r'\b((?:19|20)\d{2})\.\s*$', before)
        if category == 'report' and report_year:
            after += ' ' + report_year.group(1)
            before = before[:report_year.start()]
    before = re.split(r'Autor correspondente:|Corresponding author:', before, flags=re.I)[0].strip(' .;')
    authors = [clean(a).strip(' .;') for a in before.split(';') if clean(a)]
    if not authors and category == 'thesis':
        authors = [researcher['name']]
    # Only the citation AFTER the title is searched: a year in a paper title/event
    # must not become its publication year. Conference/book citations end in year.
    years = re.findall(r'\b(?:19|20)\d{2}\b', re.sub(r'https?://\S+', '', after))
    journal_year = re.search(r'\(((?:19|20)\d{2})\)\s*:', after) if category == 'journal' else None
    year = journal_year.group(1) if journal_year else years[-1] if years else ''
    full = re.search(r'\b((?:19|20)\d{2})[/-](\d{1,2})(?:[/-](\d{1,2}))?\b', after)
    dt = valid_date('-'.join(x for x in full.groups() if x)) if full else year
    dt = dt if not year or dt[:4] == year else year
    doi = doi_from(raw)
    links = [safe_url(n.attrs.get('href')) for n in li.nodes('a')]
    links = list(dict.fromkeys(x for x in links if x))
    if doi:
        links.insert(0, 'https://doi.org/' + doi)
    # Preserve literal URL citations too, since not every CV uses anchors.
    for u in re.findall(r'https?://[^\s<>]+', after):
        u = safe_url(u.rstrip('.,;'))
        if u and u not in links:
            links.append(u)
    italics = [clean(n.text()) for n in li.nodes('i')]
    venue = next((x for x in italics if x != title), '')
    state_text = ' '.join(clean(n.text()) for n in li.nodes('div')).casefold()
    status = 'in press' if re.search(r'no prelo|in press', state_text) else 'accepted' if re.search(r'aceite|accepted', state_text) else 'published' if re.search(r'publicado|published', state_text) else 'unspecified'
    return dict(title=title, authors=authors, type=category, date=dt, profile_year=year,
                date_source='CiênciaVitae', doi=doi, venue=venue, status=status,
                url=links[0] if links else '', links=links, researcher_ids=[researcher['id']],
                sources=[dict(name='CiênciaVitae', url=source, researcher_id=researcher['id'],
                              fetched_at=fetched_at, citation=raw, category=category)],
                raw=raw, warnings=[] if dt else ['Publication year missing'])

def parse_profile(html, profile, fetched_at):
    root = DOM(html).root
    titles = list(root.nodes('title'))
    name = clean(titles[0].text()).split(' (')[0].split(' |')[0] if titles else ''
    # Require the exact supplied identifier, not a login/error page returned as 200.
    if not name or profile['id'] not in (titles[0].text() if titles else ''):
        raise ValueError('Profile identity not found; source may be private or unavailable')
    researcher = dict(id=profile['id'], name=name, url=profile['url'], orcid='')
    for a in root.nodes('a'):
        m = re.search(r'orcid\.org/(\d{4}-\d{4}-\d{4}-[\dX]{4})', a.attrs.get('href', ''))
        if m:
            researcher['orcid'] = m.group(1); break
    # Explicit public participation entries supply attendance evidence and dates
    # independently of publication records. Do not infer attendance from authorship.
    researcher['conference_participation'] = []
    for h in root.nodes('h3'):
        if norm(h.text()) not in ('participacaoemevento', 'eventparticipation'):
            continue
        siblings = h.parent.children
        table = next((n for n in siblings[siblings.index(h)+1:] if isinstance(n, Node) and n.tag == 'table'), None)
        if table is None:
            continue
        for row in table.nodes('tr'):
            cells = [c for c in row.children if isinstance(c, Node) and c.tag == 'td']
            if len(cells) < 3:
                continue
            category = ' '.join(clean(n.text()) for n in cells[1].nodes('div'))
            if norm(category) not in ('conferencia', 'congresso', 'conference', 'congress'):
                continue
            dates = re.findall(r'\b\d{4}/\d{2}/\d{2}\b', cells[0].text())
            if not dates:
                continue
            start, end = valid_date(dates[0].replace('/', '-')), valid_date(dates[-1].replace('/', '-'))
            if not start or not end or end < start:
                continue
            researcher['conference_participation'].append(dict(name=clean(cells[2].text(omit=('div',))),
                start_date=start, end_date=end, source_url=profile['url'],
                description=clean(cells[1].text(omit=('div',)))))
    headings = [h for h in root.nodes('h3') if norm(h.text()) in ('publicacoes', 'publications')]
    if not headings:
        raise ValueError('Publication section missing; cannot establish a successful empty profile')
    heading = headings[0]
    siblings = heading.parent.children
    table = next((n for n in siblings[siblings.index(heading) + 1:] if isinstance(n, Node) and n.tag == 'table'), None)
    if table is None:
        raise ValueError('Publication table missing; source layout may have changed')
    pubs, warnings, rejected = [], [], []
    for tr in table.nodes('tr'):
        cells = [c for c in tr.children if isinstance(c, Node) and c.tag == 'td']
        if len(cells) != 2:
            continue
        label = clean(cells[0].text()); category = CATEGORY.get(norm(label), 'other')
        if category == 'other':
            warnings.append('Unmapped publication category: ' + label)
        for li in cells[1].nodes('li'):
            try:
                pubs.append(parse_citation(li, category, researcher, profile['url'], fetched_at))
            except ValueError as exc:
                rejected.append(dict(category=label, reason=str(exc), citation=clean(li.text())))
    return researcher, pubs, warnings, rejected
