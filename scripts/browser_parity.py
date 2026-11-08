"""Generate cross-runtime expectations from Python ORT, including long forms."""
import argparse,json
from pathlib import Path
from passbert.inference import Classifier
from passbert.windows import windows
from passbert.data import load
p=argparse.ArgumentParser();p.add_argument('--model',required=True);args=p.parse_args();model=Classifier(args.model)
forms=[c['expected'][i] for c in json.loads(Path('tests/robustness.json').read_text()) for i in range(len(c['expected']))]
heldout=Path(args.model).parent/'artifacts/data/test.jsonl'
if heldout.exists():forms.extend(r['form'] for r in load(heldout)[:128])
forms.append({'context':'認証 コード','fields':[{'type':'text','hint':'認証 コード','autocomplete':'one-time-code'} for _ in range(64)]})
rows=[{'form':f,'windows':[{'ids':ids,'positions':pos,'indices':indices} for ids,pos,indices in windows(model.tok,f)],'prediction':model.predict(f)} for f in forms]
Path('artifacts/automation').mkdir(parents=True,exist_ok=True);Path('artifacts/automation/parity.json').write_text(json.dumps({'model':args.model,'cases':rows},ensure_ascii=False));print(len(rows),'cross-runtime cases')
