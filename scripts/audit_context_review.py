"""Route blind opinions for adjudication without modifying labels or datasets."""
import argparse
import json
from collections import Counter
from pathlib import Path
from passbert.evidence import assess

def audit(root):
 def rows(path):
  records=list(map(json.loads,path.read_text().splitlines()));result={r['record_id']:r for r in records}
  if len(records)!=len(result):raise ValueError('Duplicate record IDs')
  return result
 requests=rows(root/'blind-local.jsonl');reviews=rows(root/'output/review-output/reviews.jsonl')
 for control in json.loads((root/'controls-local.json').read_text()):
  response=reviews.get(control['record_id'],{})
  if response.get('status')!='valid' or any(response.get(k)!=control[k] for k in ['form_label','field_labels']):raise ValueError('Control failed')
 changed={r['record_id']:r for r in json.loads((root/'paired-comparison.json').read_text())['changes']}
 cases=[];counts=Counter();reasons=Counter()
 if requests.keys()!=reviews.keys():raise ValueError('Missing or unknown review IDs')
 for key,request in requests.items():
  if request['kind']!='corpus':continue
  review=reviews[key]
  if review['status']!='valid':raise ValueError('Invalid review')
  labels={k:review[k] for k in ['form_label','field_labels']}
  decision=assess(request['form'],labels,request['annotation_policy'])
  sensitive_change=key in changed and any(changed[key]['fields_before'][i] in {'current-password','new-password','one-time-code','captcha'} or changed[key]['fields_after'][i] in {'current-password','new-password','one-time-code','captcha'} for i in changed[key]['changed_field_indices'])
  # Every change remains in the adjudication queue, including changes passing rules.
  priority=0 if sensitive_change else 1 if key in changed else 2
  counts[decision['route']]+=1;counts['changed_cases']+=key in changed;counts['sensitive_changed_cases']+=sensitive_change
  for fs in decision['field_flags']:
   reasons.update(fs)
  reasons.update(decision['form_flags'])
  cases.append({'record_id':key,'priority':priority,'changed':key in changed,'form':request['form'],'review':labels,'decision':decision})
 cases.sort(key=lambda c:(c['priority'],c['record_id']))
 (root/'adjudication-queue.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in cases))
 result={'counts':dict(counts),'reason_counts':dict(reasons),'gold_labels':0,'training_promotions':0,'accuracy_measured':False}
 (root/'evidence-audit.json').write_text(json.dumps(result,indent=2));return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',default='artifacts/context-review-v3');args=p.parse_args();print(json.dumps(audit(Path(args.root)),indent=2))
