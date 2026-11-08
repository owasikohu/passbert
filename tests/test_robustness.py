import json
import unittest
from pathlib import Path
from tokenizers import Tokenizer
from passbert.data import extract
from passbert.windows import windows

class RobustnessTests(unittest.TestCase):
    def test_development_contracts(self):
        for case in json.loads(Path('tests/robustness.json').read_text()):
            with self.subTest(case=case['name']):
                forms=extract(case['html']);self.assertEqual(forms,case['expected'])
                self.assertEqual([len(f['fields']) for f in forms],[len(y['fields']) for y in case['labels']])
    def test_training_reader_rejects_evaluation_only(self):
        import tempfile
        from passbert.data import load
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'eval.jsonl';path.write_text(json.dumps({'evaluation_only':True})+'\n')
            with self.assertRaises(ValueError):load(path)

    def test_guard_contracts(self):
        from passbert.decision import guard
        for case in json.loads(Path('tests/decision-contracts.json').read_text()):
            raw={'form':case['purpose'],'fields':[case['raw']]}
            result=guard({'fields':[case['field']]},raw)
            self.assertEqual(result['fields'],[case['expected']])
            self.assertEqual(result['guard_reasons'],[case['reason']])
            self.assertEqual(result['raw_model'],raw)

    def test_nested_sensitive_text(self):
        result=extract('<form><label><select><option><span>password</span></option></select></label><label contenteditable="true">password<input></label><!-- password --></form>')
        self.assertNotIn('password',str(result))
    def test_windows_cover_fields_once(self):
        from tokenizers import models,pre_tokenizers
        tok=Tokenizer(models.WordPiece(vocab={'[UNK]':0,'[CLS]':1,'[FLD]':2,'login':3,'current':4,'password':5,'-':6}));tok.add_special_tokens(['[CLS]','[FLD]']);tok.pre_tokenizer=pre_tokenizers.BertPreTokenizer()
        form={'context':'login','fields':[{'type':'password','hint':'current password '*8,'autocomplete':'current-password'} for _ in range(64)]}
        chunks=windows(tok,form);self.assertGreater(len(chunks),1)
        self.assertEqual([i for _,_,indices in chunks for i in indices],list(range(64)))
        for ids,pos,indices in chunks:
            self.assertLessEqual(len(ids),256);self.assertEqual(len(pos),len(indices))
            self.assertTrue(all(ids[p]==tok.token_to_id('[FLD]') for p in pos))
