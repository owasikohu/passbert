import json
import unittest
from passbert.review import blind_payload,messages,parse_labels,valid_view

class BlindReviewTests(unittest.TestCase):
    def setUp(self):
        self.form={'context':'sign in','fields':[{'type':'text','hint':'username','autocomplete':'username'}]}
        self.row={'record_id':'a'*64,'split':'train','evaluation_only':False,'form':self.form,'annotation_view':self.form}
        self.request={'record_id':'a'*64,'form':self.form,'language':'en','teacher_predictions_visible':False,'prediction':'DO_NOT_UPLOAD'}
    def test_blind_payload_has_only_allowlisted_fields(self):
        payload=blind_payload(self.request,self.row)
        self.assertEqual(set(payload),{'record_id','language','form','kind','annotation_policy'})
        self.assertNotIn('DO_NOT_UPLOAD',json.dumps(payload))
        self.assertNotIn('record_id',messages(payload)[1]['content'])
    def test_reserved_sites_and_unsafe_values_are_rejected(self):
        with self.assertRaises(ValueError):blind_payload(self.request,{**self.row,'split':'test'})
        with self.assertRaises(ValueError):blind_payload({**self.request,'teacher_predictions_visible':True},self.row)
        self.assertFalse(valid_view({'context':'sign in','fields':[{'type':'text','hint':'username','autocomplete':'','value':'SECRET'}]}))
        self.assertFalse(valid_view({'context':'PRIVATE_URL_TOKEN','fields':self.form['fields']}))
    def test_label_validation_rejects_misalignment_and_extra_text(self):
        self.assertEqual(parse_labels('{"form_label":"login","field_labels":["username"]}',1)['form_label'],'login')
        self.assertEqual(parse_labels('```json\n{"form_label":"unreviewable","field_labels":["email"]}\n```',1)['form_label'],'unreviewable')
        for text in ['{"form_label":"login","field_labels":[]}','{"form_label":"login","field_labels":["user"]}','{"form_label":"login","field_labels":["username"],"notes":"SECRET"}','This is a login form']:
            with self.assertRaises(ValueError):parse_labels(text,1)

class ReviewSummaryTests(unittest.TestCase):
    def test_abstentions_and_controls_are_separate_from_model_agreement(self):
        from scripts.summarize_review import summarize
        form={'context':'','fields':[{'type':'text','hint':'','autocomplete':''}]}
        requests=[{'record_id':'r','form':form,'language':'ja','kind':'corpus'},{'record_id':'c','form':form,'kind':'control'}]
        proposals=[{'record_id':'r','prediction':{'form':'login','fields':['username']},'decision':{'status':'agreement_candidate','field_agreement_candidates':[True]}}]
        reviews=[{'record_id':'r','status':'valid','form_label':'unreviewable','field_labels':['unreviewable']},{'record_id':'c','status':'valid','form_label':'unreviewable','field_labels':['unreviewable']}]
        controls=[{'record_id':'c','form_label':'unreviewable','field_labels':['unreviewable']}]
        r=summarize(requests,proposals,reviews,controls)
        self.assertEqual(r['counts']['abstained_or_partial'],1);self.assertEqual(r['controls']['exact'],1);self.assertEqual(r['gold_labels'],0);self.assertEqual(r['training_promotions'],0)
        with self.assertRaises(ValueError):summarize(requests,proposals,reviews+reviews,controls)

class KaggleWatchTests(unittest.TestCase):
    def test_status_calls_have_deadlines_and_do_not_hide_timeouts(self):
        import subprocess
        from unittest.mock import patch
        from passbert.kaggle_watch import kernel_status
        with patch('passbert.kaggle_watch.subprocess.run',return_value=subprocess.CompletedProcess([],0,"x has status \"KernelWorkerStatus.COMPLETE\"",'')) as run:
            self.assertEqual(kernel_status('kaggle','owner/job'),'complete');self.assertEqual(run.call_args.kwargs['timeout'],45)
        with patch('passbert.kaggle_watch.subprocess.run',side_effect=subprocess.TimeoutExpired('kaggle',45)):
            with self.assertRaises(subprocess.TimeoutExpired):kernel_status('kaggle','owner/job')
