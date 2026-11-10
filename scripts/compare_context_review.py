"""Paired annotation-view experiment; label changes are not accuracy measurements."""
import argparse
import json
from pathlib import Path

def compare(old, new):
 def rows(root,name):return {r['record_id']:r for r in map(json.loads,(root/name).read_text().splitlines())}
 a=rows(old,'blind-local.jsonl');b=rows(new,'blind-local.jsonl')
 if a.keys()!=b.keys():raise ValueError('Unpaired record IDs')
 ma=json.loads((old/'output/review-output/metadata.json').read_text());mb=json.loads((new/'output/review-output/metadata.json').read_text())
 for key in ['model','revision','quant_sha256','llama_release','prompt_sha256','reasoning_effort','reasoning_budget','max_tokens','temperature','seed','parallel']:
  if ma[key]!=mb[key]:raise ValueError('Changed experiment setting: '+key)
 if json.loads((old/'controls-local.json').read_text())!=json.loads((new/'controls-local.json').read_text()):raise ValueError('Changed control answers')
 ra=rows(old,'output/review-output/reviews.jsonl');rb=rows(new,'output/review-output/reviews.jsonl')
 if ra.keys()!=a.keys() or rb.keys()!=b.keys():raise ValueError('Missing reviews')
 changes=[];counts={'forms':0,'fields':0,'purpose_changed':0,'field_changed':0,'unknown_purpose_before':0,'unknown_purpose_after':0,'unknown_fields_before':0,'unknown_fields_after':0}
 for key in a:
  x,y=ra[key],rb[key]
  if x['status']!='valid' or y['status']!='valid':raise ValueError('Invalid reviewer output')
  n=len(a[key]['form']['fields'])
  if len(b[key]['form']['fields'])!=n or len(x['field_labels'])!=n or len(y['field_labels'])!=n:raise ValueError('Unaligned fields')
  if a[key]['kind']=='control':
   if a[key]!=b[key]:raise ValueError('Changed control input')
   continue
  counts['forms']+=1;counts['fields']+=n
  changed=[i for i in range(n) if x['field_labels'][i]!=y['field_labels'][i]]
  counts['purpose_changed']+=x['form_label']!=y['form_label'];counts['field_changed']+=len(changed)
  for suffix,r in [('before',x),('after',y)]:
   counts['unknown_purpose_'+suffix]+=r['form_label']=='unreviewable'
   counts['unknown_fields_'+suffix]+=r['field_labels'].count('unreviewable')
  if changed or x['form_label']!=y['form_label']:changes.append({'record_id':key,'purpose_before':x['form_label'],'purpose_after':y['form_label'],'changed_field_indices':changed,'fields_before':x['field_labels'],'fields_after':y['field_labels']})
 return {'counts':counts,'changes':changes,'accuracy_measured':False,'gold_labels':0,'training_promotions':0}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--old',default='artifacts/blind-review');p.add_argument('--new',default='artifacts/context-review-v3');args=p.parse_args()
 result=compare(Path(args.old),Path(args.new));(Path(args.new)/'paired-comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result['counts']))
