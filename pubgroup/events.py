"""Resolve arbitrary conference editions from metadata and sourced event pages."""
import copy
import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from .model import clean, norm, safe_url, valid_date
from .network import FetchError
from .parser import DOM
from .state import atomic_json

CONFERENCE_TYPES = {'conference', 'poster', 'abstract'}
PARTICLES = {'da', 'de', 'do', 'das', 'dos', 'e', 'van', 'von'}
MONTHS = {name: i for i, names in enumerate([
    'january janeiro', 'february fevereiro', 'march março marco', 'april abril', 'may maio',
    'june junho', 'july julho', 'august agosto', 'september setembro', 'october outubro',
    'november novembro', 'december dezembro'], 1) for name in names.split()}
MONTH_PATTERN = '|'.join(MONTHS)
STOP = {'the','a','an','of','on','in','and','for','with','international','conference','congress',
        'symposium','annual','joint','th','st','nd','rd','ieee','apca'}

def display_name(name):
    name = clean(name)
    if name.isupper():
        words = name.title().split()
        name = ' '.join(w.lower() if i and w.casefold() in PARTICLES else w for i, w in enumerate(words))
    return name

def event_key(venue, year):
    return str(year) + ':' + norm(venue)

def name_matches(venue, text, year):
    """Require a distinctive name or acronym AND the requested edition year."""
    if str(year) not in text:
        return False
    if norm(venue) and norm(venue) in norm(text):
        return True
    tokens = lambda s: {w.casefold() for w in re.findall(r'[^\W\d_]+', s) if len(w)>2 and w.casefold() not in STOP}
    v, t = tokens(venue), tokens(text)
    # Known acronym must match as a word, not a substring of another event.
    acronyms = [a for a in re.findall(r'\b([A-Z]{3,})(?:[’\' -]?\d{2,4})?\b', venue) if a.casefold() not in STOP and a != 'IFAC']
    if any(re.search(r'\b' + re.escape(a) + r'\b', text, re.I) for a in acronyms) and len(v & t)>=2:
        return True
    return len(v & t) >= 2 and (len(v & t) / max(1,len(v)) >= .6
                                     or (len(t)<=5 and len(v & t)/max(1,len(t))>=.8))

def date_parts(value):
    try:
        return valid_date('-'.join(str(x) for x in value['date-parts'][0]))
    except (KeyError, TypeError, IndexError):
        return ''

def make_event(name, start, end, url, method, year, location='', evidence=''):
    start, end = valid_date(start), valid_date(end or start)
    if len(start) != 10 or len(end) != 10 or start[:4] != str(year) or end < start:
        return None
    if (date.fromisoformat(end)-date.fromisoformat(start)).days > 31:
        return None
    return dict(status='resolved', id=hashlib.sha256((norm(name)+'|'+str(year)).encode()).hexdigest()[:16],
                name=clean(name), year=int(year), start_date=start, end_date=end, source_url=safe_url(url),
                method=method, location=clean(location), evidence=clean(evidence),
                checked_at=time.time(), confirmed_attendees=[])

def walk_json(value):
    if isinstance(value,dict):
        yield value
        for child in value.values():yield from walk_json(child)
    elif isinstance(value,list):
        for child in value:yield from walk_json(child)

def extract_event_dates(html, venue, year, url):
    """JSON-LD Event first, then unambiguous date ranges in event context.

    Registration/submission dates are excluded. Conflicting event periods are not
    reduced to a guessed month. The same algorithm applies to every conference.
    """
    root = DOM(html).root
    found = []
    for node in root.nodes('script'):
        if node.attrs.get('type') != 'application/ld+json':continue
        try: objects = list(walk_json(json.loads(node.text())))
        except ValueError:continue
        for obj in objects:
            types = obj.get('@type', [])
            if isinstance(types,str):types=[types]
            if not any(str(t).endswith('Event') for t in types):continue
            name = clean(obj.get('name'))
            if not name_matches(venue,name,year):continue
            status = str(obj.get('eventStatus',''))
            if 'Cancelled' in status or 'Postponed' in status:continue
            loc = obj.get('location', {})
            if isinstance(loc,dict):loc=loc.get('name','')
            result = make_event(name,str(obj.get('startDate',''))[:10],str(obj.get('endDate',''))[:10],
                                url,'structured event data',year,loc,'Schema.org Event startDate/endDate')
            if result:found.append(result)
    if not found:
        text=clean(root.text(omit=('script','style','noscript')))
        if not name_matches(venue,text,year):return None
        patterns = [
            rf'(?P<d1>\d{{1,2}})(?:st|nd|rd|th)?\s*(?:[-–—]|to|a)\s*(?P<d2>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:de\s+)?(?P<m>{MONTH_PATTERN})\s*,?\s*(?:de\s+)?(?P<y>\d{{4}})',
            rf'(?P<m>{MONTH_PATTERN})\s*(?P<d1>\d{{1,2}})(?:st|nd|rd|th)?\s*(?:[-–—]|to|a)\s*(?P<d2>\d{{1,2}})(?:st|nd|rd|th)?\s*,?\s*(?P<y>\d{{4}})',
            rf'(?:on|held on|takes place on)\s+(?P<d1>\d{{1,2}})\s+(?P<m>{MONTH_PATTERN})\s*,?\s*(?P<y>\d{{4}})'
        ]
        for pattern in patterns:
            for match in re.finditer(pattern,text,re.I):
                if match['y'] != str(year):continue
                before=text[max(0,match.start()-250):match.start()].lower()
                event_words=list(re.finditer(r'conference|congress|symposium|workshop|will be held|was held|take place',before))
                deadline_words=list(re.finditer(r'deadline|submission|camera.ready|notification|early.bird|registration closes',before))
                if not event_words:continue
                if deadline_words and deadline_words[-1].start()>event_words[-1].start():continue
                month=MONTHS[match['m'].lower()]
                start=f"{year}-{month:02}-{int(match['d1']):02}"
                day2=match.groupdict().get('d2') or match['d1']
                end=f"{year}-{month:02}-{int(day2):02}"
                evidence=text[max(0,match.start()-100):min(len(text),match.end()+100)]
                result=make_event(venue,start,end,url,'conference webpage',year,evidence=evidence)
                if result:found.append(result)
    dates={(r['start_date'],r['end_date']) for r in found}
    return found[0] if len(dates)==1 else None

def crossref_event(metadata, venue, year, url):
    if not name_matches(venue,clean(metadata.get('name'))+' '+str(year),year):return None
    return make_event(metadata.get('name') or venue, date_parts(metadata.get('start',{})),
                      date_parts(metadata.get('end',{})),url,'Crossref event metadata',year,
                      metadata.get('location',''))

def discover_pages(client, venue, year, config):
    # Search APIs discover URLs only. Search snippets are never date evidence.
    api_key=os.environ.get('BRAVE_SEARCH_API_KEY','')
    if config.get('web_search')!='brave' or not api_key:return []
    query=urlencode({'q':f'{venue} {year} conference official dates','count':5})
    result=client.json('https://api.search.brave.com/res/v1/web/search?'+query,
                       headers={'X-Subscription-Token':api_key})
    blocked={'linkedin.com','facebook.com','reddit.com','conferencealerts.com','wikicfp.com'}
    urls=[]
    for r in result.get('web',{}).get('results',[]):
        u=safe_url(r.get('url',''))
        if u.startswith('https://') and not any(urlsplit(u).hostname.endswith(d) for d in blocked):urls.append(u)
    return urls

def resolve_events(items, client, cache_path, config, report_only=False, researchers=None):
    path=Path(cache_path)
    cache=json.loads(path.read_text()) if path.exists() else {'version':1,'resolutions':{}}
    resolutions=cache.get('resolutions',{})
    if not config.get('enabled',True):return {}
    todo={event_key(p['venue'],p.get('profile_year') or p['date'][:4]):p for p in items
          if p['type'] in CONFERENCE_TYPES and p.get('venue') and p.get('date')}
    lookup_count=0
    for key,p in todo.items():
        venue=p['venue'];year=str(p.get('profile_year') or p['date'][:4])
        old=resolutions.get(key)
        participation=[(r, a) for r in (researchers or []) for a in r.get('conference_participation', [])
                       if a['start_date'][:4] == year and name_matches(venue,a['name']+' '+year,year)]
        # A dated participation record is useful even when the work has no DOI
        # and web search is unconfigured. Its scope remains participation dates.
        if not old or old.get('status') != 'resolved':
            periods={(a['start_date'],a['end_date']) for r,a in participation}
            if len(periods)==1:
                r,a=participation[0]
                result=make_event(a['name'],a['start_date'],a['end_date'],a['source_url'],
                                  'CV participation dates',year,evidence=a.get('description',''))
                if result:
                    resolutions[key]=old=result
        if old and old.get('status')=='resolved':
            old['confirmed_attendees']=list(dict.fromkeys(r['id'] for r,a in participation))
        if old and (report_only or (time.time()-old.get('checked_at',0)<(config.get('cache_days',90) if old['status']=='resolved' else 1)*86400)):
            continue
        alias=next((e for e in resolutions.values() if e.get('status')=='resolved' and str(e['year'])==year
                    and name_matches(venue,e['name']+' '+year,year)),None)
        if alias:
            resolutions[key]=copy.deepcopy(alias);continue
        # Already verified DOI event metadata remains usable during offline rebuilds.
        check=p.get('doi_check',{})
        result=crossref_event(check.get('event',{}),venue,year,'https://api.crossref.org/works/'+p.get('doi','')) if check.get('status')=='verified' else None
        if result:
            resolutions[key]=result;continue
        if report_only or lookup_count>=int(config.get('lookup_limit',12)):continue
        lookup_count+=1
        errors=[];candidates=[]
        try:
            query=urlencode({'query.bibliographic':f'{venue} {year}', 'rows':5})
            data=client.json('https://api.crossref.org/works?'+query)
            for work in data.get('message',{}).get('items',[]):
                r=crossref_event(work.get('event',{}),venue,year,'https://api.crossref.org/works/'+work.get('DOI',''))
                if r:candidates.append(r)
        except (FetchError,ValueError) as exc:errors.append(str(exc))
        unique={(r['start_date'],r['end_date']) for r in candidates}
        if len(unique)==1:result=candidates[0]
        elif len(unique)>1:
            resolutions[key]=dict(status='unresolved',name=venue,year=year,checked_at=time.time(),reason='Conflicting event metadata');continue
        if not result:
            urls=([old['source_url']] if old and old.get('source_url') else [])
            urls += [u for u in p.get('links',[]) if u.startswith('https://') and 'doi.org' not in u and not u.endswith('.pdf')]
            urls += [s['url'] for s in config.get('sources',[]) if str(s['year'])==year and norm(s['venue'])==norm(venue)]
            try:urls+=discover_pages(client,venue,year,config)
            except (FetchError,ValueError) as exc:errors.append(str(exc))
            for url in list(dict.fromkeys(urls))[:5]:
                try:
                    client.allowed(url)
                    html,_=client.get(url)
                    found=extract_event_dates(html,venue,year,url)
                    if found:candidates.append(found)
                except (FetchError,ValueError) as exc:errors.append(str(exc))
            unique={(r['start_date'],r['end_date']) for r in candidates}
            if len(unique)==1:result=candidates[0]
        resolutions[key]=result or dict(status='unresolved',name=venue,year=year,checked_at=time.time(),
            reason='No unambiguous sourced event date found',errors=errors,
            web_search_available=bool(os.environ.get('BRAVE_SEARCH_API_KEY')))
    if not report_only:atomic_json(path,dict(version=1,resolutions=resolutions))
    return resolutions

def annotate(items, calendar):
    for p in items:
        p.pop('event', None)
        p['activity_date']=p.get('date','');p['activity_date_source']='publication'
        event=calendar.get(event_key(p.get('venue',''),p.get('profile_year') or p.get('date','')[:4]))
        if p['type'] not in CONFERENCE_TYPES or not event or event['status']!='resolved':continue
        p['event']=copy.deepcopy(event)
        if len(p.get('date',''))<7 and p['date'][:4]==event['start_date'][:4]:
            p['activity_date']=event['start_date'][:7];p['activity_date_source']='conference'

def conferences(items):
    grouped={}
    for p in items:
        if p['type'] not in CONFERENCE_TYPES or not p.get('venue'):continue
        event=p.get('event',{});year=p.get('profile_year') or p.get('date','')[:4]
        key=event.get('id') or event_key(p['venue'],year)
        g=grouped.setdefault(key,dict(id=key,name=event.get('name') or p['venue'],start_date=event.get('start_date',''),
            end_date=event.get('end_date',''),year=year,location=event.get('location',''),source_url=event.get('source_url',''),
            confirmed_attendees=event.get('confirmed_attendees',[]),publications=[],types=Counter()))
        g['publications'].append(p['id']);g['types'][p['type']]+=1
    return sorted(grouped.values(),key=lambda e:(e['start_date'] or str(e['year']),e['name']),reverse=True)
