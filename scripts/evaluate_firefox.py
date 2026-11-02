"""Summarize exported evaluation-only JSONL without importing it into training."""
import argparse
import json
from collections import Counter
from pathlib import Path
from passbert.data import FIELDS,FORMS
from passbert.metrics import score
p=argparse.ArgumentParser();p.add_argument('jsonl');p.add_argument('--output',default='artifacts/real-site-report.json');args=p.parse_args()
records=[json.loads(line) for line in Path(args.jsonl).read_text().splitlines() if line.strip()]
seen=set()
for r in records:
    if not r.get('evaluation_only') or r.get('source')!='firefox-manual-v1':raise ValueError('Not a Firefox evaluation record')
    if r['snapshot_id'] in seen:raise ValueError('Duplicate snapshot; do not concatenate the same export twice')
    seen.add(r['snapshot_id'])
def summarize(items):
    ft=[];fp=[];yt=[];yp=[];failed=0;total=0;unreviewable=0
    for record in items:
        for row in record['rows']:
            total+=1
            if not row['prediction']:failed+=1;continue
            if row['form_label']!='unreviewable':yt.append(row['form_label']);yp.append(row['prediction']['form'])
            else:unreviewable+=1
            if len(row['field_labels'])!=len(row['prediction']['fields']):raise ValueError('Field alignment mismatch')
            for a,b in zip(row['field_labels'],row['prediction']['fields']):
                if a!='unreviewable':ft.append(a);fp.append(b)
    return {'pages':len(items),'sites':len({r['site_id'] for r in items}),'forms_extracted':total,'forms_inference_failed':failed,'forms_unreviewable':unreviewable,'forms_scored':len(yt),'fields_scored':len(ft),'form':score(yt,yp,FORMS),'field':score(ft,fp,FIELDS)}
models=Counter(json.dumps(r['model'].get('sha256',{}),sort_keys=True) for r in records)
report={'scope':'manually sampled top-frame forms, not extraction-recall benchmark; failed predictions excluded and counted','overall':summarize(records),'by_language':{lang:summarize([r for r in records if r['language']==lang]) for lang in sorted({r['language'] for r in records})},'model_hashes':dict(models),'warning':'Different captures of the same page/template may be correlated. Use host groups and independent sites; never train on this evaluation set.'}
out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report['overall'],ensure_ascii=False,indent=2))
