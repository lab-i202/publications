"""General date discovery, chronology, privacy and source-evidence regressions."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pubgroup.events import extract_event_dates, resolve_events, annotate, event_key, display_name
from pubgroup.model import metrics, sort_key
from pubgroup.network import Client

VENUE='Novel Systems Conference (NSC 2031)'
def record(kind='conference'):
    return dict(id='new',title='A new contribution',type=kind,date='2031',profile_year='2031',
                venue=VENUE,links=[],researcher_ids=['r'],status='unspecified')
PAGE='''<title>Novel Systems Conference 2031</title>
<script type="application/ld+json">{"@type":"Event","name":"Novel Systems Conference (NSC 2031)",
"startDate":"2031-09-12","endDate":"2031-09-14","location":{"name":"Coimbra"}}</script>'''

class EventTests(unittest.TestCase):
    def test_new_conference_discovered_without_named_rule(self):
        class Fake:
            def json(self,url,headers=None):
                if 'search.brave.com' in url:
                    return {'web':{'results':[{'url':'https://nsc2031.example/'}]}}
                return {'message':{'items':[]}}
            def allowed(self,url):pass
            def get(self,*a):return PAGE,{'cached':False}
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'test-only-key'}):
            path=Path(tmp)/'events.json';r=record()
            cache=resolve_events([r],Fake(),path,{'enabled':True,'web_search':'brave'})
            e=cache[event_key(VENUE,2031)]
            self.assertEqual(e['start_date'],'2031-09-12')
            self.assertEqual(e['source_url'],'https://nsc2031.example/')
            self.assertEqual(e['method'],'structured event data')
            annotate([r],cache)
            self.assertEqual(r['date'],'2031');self.assertEqual(r['activity_date'],'2031-09')
            self.assertEqual(metrics([r])['conference_months'],{'2031-09':1})
    def test_crossref_without_search_key(self):
        class Fake:
            def json(self,*args,**kwargs):return {'message':{'items':[{'DOI':'10.1234/work','event':{
                'name':VENUE,'start':{'date-parts':[[2031,9,12]]},'end':{'date-parts':[[2031,9,14]]}}}]}}
        with tempfile.TemporaryDirectory() as tmp:
            cache=resolve_events([record()],Fake(),Path(tmp)/'cache',{})
            self.assertEqual(cache[event_key(VENUE,2031)]['method'],'Crossref event metadata')
    def test_submission_deadlines_excluded(self):
        text='<title>'+VENUE+'</title><p>Submission deadline May 1-3, 2031. The conference will be held September 12-14, 2031.</p>'
        e=extract_event_dates(text,VENUE,2031,'https://nsc.example/')
        self.assertEqual(e['start_date'],'2031-09-12')
    def test_ambiguous_dates_not_guessed(self):
        text='<title>'+VENUE+'</title><p>Conference September 12-14, 2031. Conference September 19-21, 2031.</p>'
        self.assertIsNone(extract_event_dates(text,VENUE,2031,'https://nsc.example/'))
    def test_shared_acronym_with_different_name_is_rejected(self):
        other=PAGE.replace('Novel Systems Conference','Neuroscience Congress')
        self.assertIsNone(extract_event_dates(other,VENUE,2031,'https://other.example/'))
    def test_wrong_edition_or_cancelled_event_not_used(self):
        self.assertIsNone(extract_event_dates(PAGE.replace('2031','2030'),VENUE,2031,'https://nsc.example/'))
        cancelled=PAGE.replace('"@type":"Event"','"@type":"Event","eventStatus":"EventCancelled"')
        self.assertIsNone(extract_event_dates(cancelled,VENUE,2031,'https://nsc.example/'))
    def test_missing_evidence_remains_unknown(self):
        class Fake:
            def json(self,*a,**k):return {'message':{'items':[]}}
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':''}):
            r=record();cache=resolve_events([r],Fake(),Path(tmp)/'cache',{'web_search':'brave'})
            annotate([r],cache);self.assertEqual(r['activity_date'],'2031')
            self.assertEqual(cache[event_key(VENUE,2031)]['status'],'unresolved')
    def test_published_month_and_non_conference_dates_preserved(self):
        e=extract_event_dates(PAGE,VENUE,2031,'https://nsc.example/')
        cache={event_key(VENUE,2031):e}
        a,b=record(),record('journal');a['date']='2031-04';annotate([a,b],cache)
        self.assertEqual(a['activity_date'],'2031-04');self.assertEqual(b['activity_date'],'2031')
        c=record();annotate([c],cache);self.assertGreater(sort_key(c),sort_key(a))
    def test_uppercase_names_with_portuguese_particles(self):
        self.assertEqual(display_name('LUÍS TIAGO DE FREIXO RAMOS PAIVA'),'Luís Tiago de Freixo Ramos Paiva')
        self.assertEqual(display_name('José da Costa'),'José da Costa')
    def test_secret_headers_are_sent_via_stdin(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            client=Client(tmp,{'delay_seconds':0})
            def fake_run(cmd,**kwargs):
                self.assertNotIn('secret-api-token',' '.join(cmd))
                self.assertIn('secret-api-token',kwargs['input'])
                Path(cmd[cmd.index('-o')+1]).write_text('{}')
                return SimpleNamespace(stdout='200',stderr='',returncode=0)
            with patch('pubgroup.network.subprocess.run',side_effect=fake_run):
                self.assertEqual(client.json('https://api.example/search',headers={'X-Subscription-Token':'secret-api-token'}),{})



class ParticipationTests(unittest.TestCase):
    def test_dated_cv_participation_resolves_without_search_or_doi(self):
        r={'id':'r','conference_participation':[{'name':VENUE,'start_date':'2031-09-12','end_date':'2031-09-14',
             'source_url':'https://cv.example/r','description':'Participant'}]}
        with tempfile.TemporaryDirectory() as tmp:
            result=resolve_events([record()],object(),Path(tmp)/'cache',{},researchers=[r])
            event=result[event_key(VENUE,2031)]
            self.assertEqual(event['method'],'CV participation dates')
            self.assertEqual(event['confirmed_attendees'],['r'])
    def test_explicit_participation_parsed_separately_from_publications(self):
        from pubgroup.parser import parse_profile
        page='''<title>José Silva (AAAA-BBBB-CCCC) | CIÊNCIAVITAE</title>
        <h3>Publicações</h3><table><tr><td>Artigo em conferência</td><td><li>A. "A paper". 2031.</li></td></tr></table>
        <h3>Participação em evento</h3><table><tr><td>2031/09/12 - 2031/09/14</td>
        <td>Participant<div>Conferência</div></td><td>Novel Systems Conference (NSC 2031)</td></tr></table>'''
        r,items,*_=parse_profile(page,{'id':'AAAA-BBBB-CCCC','url':'https://www.cienciavitae.pt/portal/AAAA-BBBB-CCCC'},'now')
        self.assertEqual(len(items),1);self.assertEqual(len(r['conference_participation']),1)
        self.assertEqual(r['conference_participation'][0]['start_date'],'2031-09-12')

if __name__=='__main__':unittest.main()
