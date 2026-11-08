import argparse,json
from pathlib import Path
from passbert.data import extract
from passbert.inference import Classifier
from passbert.decision import guard
p=argparse.ArgumentParser();p.add_argument('--model',default='artifacts/kaggle-output/model');p.add_argument('--output',default='artifacts/robustness.json');p.add_argument('--require-raw',type=int,default=0);p.add_argument('--require-guarded',type=int,default=0);args=p.parse_args()
model=Classifier(args.model);results=[]
for case in json.loads(Path('tests/robustness.json').read_text()):
 forms=extract(case['html']);aligned=len(forms)==len(case['labels']) and all(len(f['fields'])==len(y['fields']) for f,y in zip(forms,case['labels']))
 predictions=[model.predict(f) for f in forms]
 exact=aligned and all(p['form']==y['form'] and p['fields']==y['fields'] for p,y in zip(predictions,case['labels']))
 results.append({'name':case['name'],'extraction_aligned':aligned,'exact':exact,'predictions':predictions,'guarded':[guard(f,p) for f,p in zip(forms,predictions)],'forms':forms})
for result,case in zip(results,json.loads(Path('tests/robustness.json').read_text())):
 result['guarded_exact']=result['extraction_aligned'] and all(p['form']==y['form'] and p['fields']==y['fields'] for p,y in zip(result['guarded'],case['labels']))
r={'guarded_exact':sum(x['guarded_exact'] for x in results),'scope':'development regression fixtures, consulted during improvements; not independent test accuracy','cases':len(results),'extraction_aligned':sum(x['extraction_aligned'] for x in results),'exact':sum(x['exact'] for x in results),'results':results};Path(args.output).write_text(json.dumps(r,ensure_ascii=False,indent=2));print({k:v for k,v in r.items() if k!='results'})

if r['exact']<args.require_raw or r['guarded_exact']<args.require_guarded:raise SystemExit('Regression gate failed')
