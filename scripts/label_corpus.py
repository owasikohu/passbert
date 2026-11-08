"""Label a train-only pilot locally; keep all outputs as proposals pending quality audit."""
import argparse
import json
import random
import time
from collections import Counter,defaultdict
from pathlib import Path
from passbert.labeling import ZapTeacher,ZAP_REVISION,route
from passbert.train import heuristic

p=argparse.ArgumentParser();p.add_argument('--input',default='artifacts/corpus-10k/train.jsonl');p.add_argument('--output',default='artifacts/corpus-10k/label-pilot');p.add_argument('--limit',type=int,default=500);p.add_argument('--teacher',default='artifacts/hf/hub/models--ProCreations--Zap/snapshots/'+ZAP_REVISION);args=p.parse_args()
rows=[json.loads(line) for line in Path(args.input).read_text().splitlines() if line]
if any(r.get('split')!='train' or r.get('evaluation_only') for r in rows):raise SystemExit('Only training split may receive these teacher proposals')
groups=defaultdict(list)
for row in rows:groups[(row['language'],row['bucket'])].append(row)
rng=random.Random(20261109)
for group in groups.values():rng.shuffle(group)
selected=[]
while len(selected)<min(args.limit,len(rows)):
 for key in sorted(groups):
    if groups[key] and len(selected)<args.limit:selected.append(groups[key].pop())
root=Path(args.output);root.mkdir(parents=True,exist_ok=True);teacher=ZapTeacher(args.teacher);counts=Counter();started=time.monotonic();proposals=[]
with (root/'proposals.jsonl').open('w') as output:
 for row in selected:
    view=row.get('annotation_view',row['form'])
    prediction=teacher.predict(view);no_ac=teacher.predict(view,without_autocomplete=True);rule=heuristic(view);decision=route(view,prediction,rule,no_ac)
    proposal={'record_id':row['record_id'],'site_id':row['site_id'],'split':'train','language':row['language'],'bucket':row['bucket'],'form':view,'annotation_policy':row.get('annotation_policy','privacy-v1'),'label_status':'proposal','teacher':{'model':'ProCreations/Zap','revision':ZAP_REVISION,'input_scope':'closed semantic vocabulary; not native full DOM extraction'},'prediction':prediction,'prediction_without_autocomplete':no_ac,'heuristic':{'form':rule[0],'fields':rule[1]},'decision':decision}
    output.write(json.dumps(proposal,ensure_ascii=False)+'\n');output.flush();proposals.append(proposal)
    counts['fields_total']+=len(prediction['fields']);counts['field_agreement_candidates']+=sum(decision['field_agreement_candidates']);counts['annotation_policy:'+row.get('annotation_policy','privacy-v1')]+=1
    counts[decision['status']]+=1;counts['language:'+row['language']]+=1;counts['bucket:'+row['bucket']]+=1
    if len(proposals)%25==0:print(json.dumps({'labeled':len(proposals),'seconds':round(time.monotonic()-started),'routing':dict(counts)}),flush=True)
# A stratified sample for independent review; confidence is not a quality estimate.
review=[]
for status in ['agreement_candidate','disagreement_review','low_confidence_review','autocomplete_dependence_review','taxonomy_review']:
 candidates=[r for r in proposals if r['decision']['status']==status];rng.shuffle(candidates);review.extend(candidates[:20])
(root/'review-sample.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in review))
# Blind review payload deliberately omits teacher/rule predictions.
requests=[{'record_id':r['record_id'],'language':r['language'],'form':r['form'],'task':'Independently label purpose and each field; abstain when context is insufficient. Never treat autocomplete as guaranteed correct.','teacher_predictions_visible':False,'allowed_form_labels':teacher.form_names+['unreviewable'],'allowed_field_labels':teacher.field_names+['unreviewable'],'response_schema':{'record_id':'copy input record_id','form_label':'one allowed label','field_labels':'one allowed label per input field, in order','notes':'optional uncertainty explanation'}} for r in review]
(root/'blind-review-requests.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in requests))
report={'proposals':len(proposals),'routing':dict(counts),'review_sample':len(review),'verified_labels':0,'training_eligible':0,'seconds':round(time.monotonic()-started,2),'teacher_revision':ZAP_REVISION,'limitations':['Restricted semantic vocabulary can remove decisive context','Teacher and attribute heuristic are correlated, not independent reviewers','Confidence thresholds are uncalibrated on this corpus','No labels generated for validation/test; these remain reserved','agreement_candidate is not automatically accepted or gold']}
(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False),flush=True)
