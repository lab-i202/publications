"""Regression tests for source parsing, duplicate records, changes and reports."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pubgroup.parser import parse_profile
from pubgroup.model import deduplicate, equivalent, metrics, select, sort_key, tex_escape, bibtex
from pubgroup.enrich import apply_metadata
from pubgroup.state import reconcile
from pubgroup.export import encrypt_payload, build_web
from pubgroup.report import render_tex

PROFILE = {'id':'AAAA-BBBB-CCCC','url':'https://www.cienciavitae.pt/portal/AAAA-BBBB-CCCC'}
def html(citations, label='Artigo em revista'):
    return f'<html><head><title>José Silva (AAAA-BBBB-CCCC) | CIÊNCIAVITAE</title></head><body><h3>Publicações</h3><table><tr><td>{label}</td><td><ol>{citations}</ol></td></tr></table><h3>Atividades</h3><table><tr><td><li>"Not a publication". 2026.</li></td></tr></table></body></html>'
def citation(text, label='Artigo em revista'):
    return parse_profile(html('<li>'+text+'</li>', label), PROFILE, '2026-10-13T12:00:00Z')[1][0]
def p(title='Paper', year='2026', doi='', kind='journal'):
    text=f'Alice; Bob. "{title}". <i>Journal</i> 10 ( {year} ): 1.'
    if doi:text+=f'<div>Publicado • {doi}</div>'
    item=citation(text); item.update(date=year,profile_year=year,doi=doi,type=kind)
    return item

class ParserTests(unittest.TestCase):
    def test_scope_and_identity(self):
        r,pubs,w,rejected=parse_profile(html('<li>A. "Real paper". <i>Journal</i> (2026): 1.</li>'),PROFILE,'now')
        self.assertEqual([x['title'] for x in pubs],['Real paper'])
        with self.assertRaises(ValueError):parse_profile('<title>Login</title>',PROFILE,'now')
    def test_article_number_is_not_year(self):
        item=citation('Roque, Luís. "A result". <i>Energies</i> 10 12 (2017): 2029. <div>10.3390/en10122029</div>')
        self.assertEqual(item['date'],'2017')
    def test_event_year_and_status(self):
        item=citation('A; B. Autor correspondente: A. "An event 2024". Trabalho apresentado em <i>CONTROLO 2024</i>, 2025.<div>No prelo</div>','Artigo em conferência')
        self.assertEqual(item['date'],'2025');self.assertEqual(item['status'],'in press');self.assertEqual(item['authors'],['A','B'])
    def test_italic_and_report_year(self):
        item=citation('Vinha, Sérgio. 2020. <i>Activities report</i>.','Relatório')
        self.assertEqual(item['title'],'Activities report');self.assertEqual(item['date'],'2020')
    def test_thesis_author_and_bibtype(self):
        item=citation('"A thesis". Mestrado, University, 2025.','Tese / Dissertação')
        self.assertEqual(item['authors'],['José Silva']);item=deduplicate([item])[0]
        self.assertTrue(bibtex(item).startswith('@mastersthesis'))
    def test_rejected_is_audited(self):
        self.assertEqual(len(parse_profile(html('<li>Unreadable</li>'),PROFILE,'now')[3]),1)
    def test_no_contact_data(self):
        r,items,*_=parse_profile(html('<li>A. "Work". 2026.</li>')+'<p>private@example.com</p>',PROFILE,'now')
        self.assertNotIn('private@example.com',json.dumps([r,items]))

class DataTests(unittest.TestCase):
    def test_cross_profile_merge(self):
        a=p(doi='10.1234/example');b=copy.deepcopy(a);b['researcher_ids']=['DDDD'];b['sources'][0]['researcher_id']='DDDD'
        out=deduplicate([a,b]);self.assertEqual(len(out),1);self.assertEqual(len(out[0]['researcher_ids']),2)
    def test_container_doi_does_not_merge_distinct_abstracts(self):
        a=p('Vision control of an aircraft',doi='10.1234/book',kind='abstract');b=p('Power smoothing in a wind farm',doi='10.1234/book',kind='abstract')
        out=deduplicate([a,b]);self.assertEqual(len(out),2);self.assertNotEqual(out[0]['id'],out[1]['id'])
    def test_distinct_year_kind_and_doi(self):
        self.assertEqual(len(deduplicate([p(year='2024'),p(year='2025',kind='chapter'),p(doi='10.1234/a'),p(doi='10.1234/b')])),4)
    def test_chronology_unknown_month(self):
        records=deduplicate([p('Unknown','2026'),p('March','2026-03'),p('February','2026-02-20'),p('Old','2025-12')])
        self.assertEqual([x['title'] for x in records],['March','February','Unknown','Old'])
        self.assertEqual(metrics(records)['unknown_month'],1)
    def test_periods(self):
        items=[p(year='2026'),p(year='2025'),p(year='2024')]
        self.assertEqual(len(select(items,{'period':'current'},2026)),1)
        self.assertEqual(len(select(items,{'period':'all'},2026)),3)
        self.assertEqual(len(select(items,{'period':'range','start_year':2024,'end_year':2025},2026)),2)
        self.assertEqual(len(select(items,{'period':'2025'},2026)),1)
        with self.assertRaises(ValueError):select(items,{'period':'range','start_year':2026,'end_year':2024},2026)
    def test_first_run_and_changes(self):
        items=deduplicate([p()]);changes=reconcile(items,None,'first');self.assertTrue(changes['baseline']);self.assertFalse(changes['new'])
        previous={'publications':copy.deepcopy(items)};items[0]['status']='published';items+=deduplicate([p('New paper')])
        changes=reconcile(items,previous,'second');self.assertEqual(len(changes['new']),1);self.assertEqual(len(changes['updated']),1)
    def test_doi_upgrade_keeps_identity(self):
        first=deduplicate([p()]);reconcile(first,None,'first');second=deduplicate([p(doi='10.1234/upgraded')]);changes=reconcile(second,{'publications':first},'second')
        self.assertFalse(changes['new']);self.assertEqual(second[0]['id'],first[0]['id'])
    def test_publisher_dates_and_conflicts(self):
        item=p();m=dict(source='Crossref',title='Paper',date='2025-12-01')
        apply_metadata(item,m,'profile');self.assertEqual(item['date'],'2026');self.assertTrue(item['warnings'])
        apply_metadata(item,m,'publisher');self.assertEqual(item['date'],'2025-12-01')
    def test_conflicting_title_not_applied_to_bibtex(self):
        item=deduplicate([p(doi='10.1234/wrong')])[0];item['url']='https://doi.org/10.1234/wrong'
        apply_metadata(item,dict(source='Crossref',title='Completely unrelated paper title',date='1999'),'publisher')
        self.assertEqual(item['date'],'2026');self.assertEqual(item['url'],'');self.assertNotIn('doi =',bibtex(item))
    def test_tex_escaping(self):
        self.assertEqual(tex_escape('A & B_1 50%'),r'A \& B\_1 50\%')

class ExportTests(unittest.TestCase):
    def test_encryption_roundtrip_and_tamper(self):
        try:from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError:self.skipTest('optional cryptography not installed')
        import base64,hashlib
        from cryptography.exceptions import InvalidTag
        b=encrypt_payload({'title':'José','pdf':'ABC'},'a sufficiently long test passphrase')
        key=hashlib.pbkdf2_hmac('sha256',b'a sufficiently long test passphrase',base64.b64decode(b['salt']),b['iterations'],32)
        data=base64.b64decode(b['ciphertext']);iv=base64.b64decode(b['iv'])
        self.assertEqual(json.loads(AESGCM(key).decrypt(iv,data,b'PublicationGroup:v1')),{'title':'José','pdf':'ABC'})
        with self.assertRaises(InvalidTag):AESGCM(key).decrypt(iv,data[:-1]+bytes([data[-1]^1]),b'PublicationGroup:v1')
        with self.assertRaises(ValueError):encrypt_payload({},'short')
    def test_encrypted_export_removes_plain_outputs(self):
        try:import cryptography
        except ImportError:self.skipTest('optional cryptography not installed')
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);pdf=d/'original.pdf';pdf.write_bytes(b'PDF DATA');web=d/'web';web.mkdir()
            for n in ('publications.json','report.pdf','publications.bib'): (web/n).write_text('secret')
            build_web({'publications':[]},pdf,web,'a sufficiently long test passphrase')
            self.assertFalse((web/'publications.json').exists());self.assertFalse((web/'report.pdf').exists());self.assertFalse((web/'publications.bib').exists())
            manifest = json.loads((web/'manifest.json').read_text())
            self.assertTrue(manifest['encrypted'])
            self.assertRegex(manifest['revision'], r'^[0-9a-f]{64}$')
            old_revision = manifest['revision']
            build_web({'publications':[]},pdf,web,'a sufficiently long test passphrase')
            self.assertNotEqual(json.loads((web/'manifest.json').read_text())['revision'], old_revision)


class WorkflowTests(unittest.TestCase):
    def test_failed_source_retains_records_and_does_not_create_new(self):
        from pubgroup.workflow import run
        from pubgroup.network import FetchError
        cfg='''[group]
name="Test group"
timezone="Europe/Lisbon"
[report]
period="current"
[network]
[enrichment]
enabled=false
[output]
compile_pdf=false
[[researchers]]
id="AAAA-BBBB-CCCC"
url="https://www.cienciavitae.pt/portal/AAAA-BBBB-CCCC"
'''
        class Fake:
            fail=False
            def __init__(self,*a):pass
            def allowed(self,*a):pass
            def get(self,*a):
                if self.fail:raise FetchError('Temporary source outage')
                return html('<li>A. "Work". <i>Journal</i> (2026): 1.</li>'),dict(timestamp=1791880000,cached=False)
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/'config.toml';config.write_text(cfg)
            with patch('pubgroup.workflow.Client',Fake):
                first=run(config,no_pdf=True);Fake.fail=True;second=run(config,no_pdf=True)
            self.assertEqual(len(first['catalogue']),1);self.assertEqual(len(second['catalogue']),1)
            self.assertEqual(second['sources'][0]['status'],'unavailable')
            self.assertFalse(second['changes']['new']);self.assertFalse(second['changes']['no_longer_listed'])
    def test_process_lock_rejects_concurrent_build(self):
        from pubgroup.locking import OperationLock
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'lock'
            with OperationLock(path):
                with self.assertRaises(RuntimeError):
                    with OperationLock(path):pass



class ReferenceTests(unittest.TestCase):
    def test_zotero_matches_only_similar_titles_and_ignores_attachments(self):
        from pubgroup.enrich import review_zotero
        class Fake:
            def get(self,*args):
                return json.dumps([
                    {'data':{'title':'Paper','DOI':'10.1234/example','itemType':'journalArticle'}},
                    {'data':{'title':'Unrelated work','DOI':'10.1234/example','itemType':'journalArticle'}},
                    {'data':{'title':'PDF attachment','itemType':'attachment'}}
                ]), dict(timestamp=1791880000,cached=True)
        out=review_zotero([p(doi='10.1234/example')],Fake(),'5341747')
        self.assertEqual(out['items'],2);self.assertEqual(out['matched'],1);self.assertEqual(len(out['review']),1)
        self.assertTrue(out['review'][0]['requires_review'])
    def test_failed_encryption_keeps_previous_public_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            web=Path(tmp);(web/'publications.json').write_text('original data')
            with patch('pubgroup.export.encrypt_payload',side_effect=RuntimeError('dependency missing')):
                with self.assertRaises(RuntimeError):build_web({'publications':[]},None,web,'long test phrase for encryption')
            self.assertEqual((web/'publications.json').read_text(),'original data')

if __name__=='__main__':unittest.main()
