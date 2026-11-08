import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

class ReportTest(unittest.TestCase):
    def test_report_counts_failures_and_ignores_unreviewable(self):
        record={'schema_version':1,'snapshot_id':'test','evaluation_only':True,'source':'firefox-manual-v1','site_id':'hash','language':'ja','model':{'sha256':{'model':'fixed'}},'rows':[{'form_label':'login','field_labels':['email','unreviewable'],'prediction':{'form':'signup','fields':['email','other'],'raw_model':{'form':'signup','fields':['other','other']}}},{'form_label':'otp','field_labels':['one-time-code'],'prediction':None}]}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'evaluation.jsonl').write_text(json.dumps(record)+'\n')
            proc=subprocess.run([sys.executable,'-m','scripts.evaluate_firefox',str(root/'evaluation.jsonl'),'--output',str(root/'report.json')],capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            whole=json.loads((root/'report.json').read_text());report=whole['overall']
            self.assertEqual(whole['raw_model']['field']['accuracy'],0)
            self.assertEqual(report['forms_inference_failed'],1)
            self.assertEqual(report['forms_scored'],1)
            self.assertEqual(report['fields_scored'],1)
            self.assertEqual(report['form']['accuracy'],0)
            self.assertEqual(report['field']['accuracy'],1)
