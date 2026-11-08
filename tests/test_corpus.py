import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

@unittest.skipUnless(importlib.util.find_spec('tldextract'),'corpus extra is not installed')
class CorpusTests(unittest.TestCase):
    def test_site_identity_ignores_paths_and_query_values(self):
        from passbert.corpus import identity
        a=identity('https://login.example.co.jp/login?token=PRIVATE')
        b=identity('https://accounts.example.co.jp/another?secret=SECRET')
        self.assertEqual(a[0],b[0]);self.assertEqual(a[2],b[2]);self.assertNotEqual(a[1],b[1])
        self.assertNotEqual(identity('https://alice.github.io')[0],identity('https://bob.github.io')[0])
    def test_canonical_dedup_and_site_cap(self):
        from passbert.corpus import Corpus,canonical
        form={'context':'login login','fields':[{'type':'text','hint':'username username','autocomplete':'username'}]}
        other={'context':'login','fields':[{'type':'text','hint':'username','autocomplete':'username'}]}
        self.assertEqual(canonical(form),canonical(other))
        with tempfile.TemporaryDirectory() as directory:
            db=Corpus(Path(directory)/'db.sqlite')
            row={'record_id':'r','site_id':'site','split':'train','language':'en','language_basis':'html-lang','bucket':'auth-candidate','template_family':canonical(form),'form':form}
            self.assertEqual(db.insert(row), 'accepted');self.assertEqual(db.insert(row),'duplicate')
            another={**row,'template_family':'other'};self.assertEqual(db.insert(another,max_per_site=1),'site_cap')
            result=db.export(Path(directory)/'out');self.assertEqual(result['site_overlap'],0)
            self.assertEqual(result['counts']['total'],1)
    def test_unlabeled_and_proposals_cannot_be_used_as_training_labels(self):
        from passbert.data import load
        with tempfile.TemporaryDirectory() as directory:
            for status in ['unlabeled','proposal']:
                path=Path(directory)/'data.jsonl';path.write_text(json.dumps({'label_status':status})+'\n')
                with self.assertRaises(ValueError):load(path)

    def test_annotation_view_never_reads_values(self):
        from passbert.data import extract
        views=[]
        forms=extract('<form><label>First name<input value="password"></label><textarea>email</textarea><h2 contenteditable="true">username</h2></form>',_annotation_views=views)
        self.assertEqual(len(forms[0]['fields']),len(views[0]['fields']))
        self.assertEqual(views[0]['fields'][0]['hint'],'first name')
        self.assertNotIn('password',str(views));self.assertNotIn('email',str(views));self.assertNotIn('username',str(views))

    def test_fast_parser_privacy_and_parity(self):
        if not importlib.util.find_spec('selectolax') or not importlib.util.find_spec('lxml'):self.skipTest('fast parser not installed')
        from selectolax.lexbor import LexborHTMLParser
        from passbert.fast_extract import extract_fast
        from passbert.data import extract
        for case in json.loads(Path('tests/robustness.json').read_text())+json.loads(Path('tests/extraction-fixtures.json').read_text()):
            self.assertEqual(extract(LexborHTMLParser(case['html']).html,_parser='lxml'),case['expected'])
            native,views=extract_fast(case['html']);reference_views=[]
            self.assertEqual(native,case['expected'])
            extract(case['html'],_annotation_views=reference_views)
            self.assertEqual(views,reference_views)
        form=extract(LexborHTMLParser('<form><input value="PRIVATE"><textarea>SECRET</textarea><input type="hidden" value="TOKEN"></form>').html,_parser='lxml')
        self.assertFalse(any(word in str(form) for word in ['PRIVATE','SECRET','TOKEN']))
        native,views=extract_fast('<form><input value="password"><textarea>email</textarea><select><option>username</option></select></form>')
        self.assertFalse(any(word in str(views) for word in ['password','email','username']))

class RoutingTests(unittest.TestCase):
    def test_agreement_is_not_a_verified_label(self):
        from passbert.label_policy import route
        pred={'form':'login','fields':['username'],'form_confidence':.99,'field_confidences':[.99]}
        result=route({},pred,('login',['username']),pred)
        self.assertEqual(result['status'],'agreement_candidate');self.assertFalse(result['verified']);self.assertFalse(result['training_eligible'])
        result=route({},pred,('login',['email']),pred);self.assertEqual(result['status'],'disagreement_review')
        ablated={**pred,'fields':['email']}
        self.assertEqual(route({},pred,('login',['username']),ablated)['status'],'autocomplete_dependence_review')
        other={**pred,'form':'payment'};self.assertEqual(route({},other,('other',['username']),other)['status'],'taxonomy_review')
