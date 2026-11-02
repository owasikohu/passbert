"""Restricted-input comparison, without executing remote repository code."""
import argparse
import json
import time
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification
from passbert.data import FIELDS, FORMS, load
from passbert.train import evaluate

p=argparse.ArgumentParser(); p.add_argument('--revision',default='0ab38d45793577230569ad77e0e52fcdfb67b9dc'); p.add_argument('--data',default='artifacts/data/test.jsonl'); p.add_argument('--output',default='artifacts/zap-report.json'); args=p.parse_args()
torch.set_num_threads(2)
start=time.perf_counter()
tok=AutoTokenizer.from_pretrained('ProCreations/Zap',revision=args.revision,trust_remote_code=False)
model=AutoModelForTokenClassification.from_pretrained('ProCreations/Zap',revision=args.revision,trust_remote_code=False).float().eval()
labels=model.config.id2label
form_ids=[i for i,l in labels.items() if l.startswith('form:')]; field_ids=[i for i,l in labels.items() if l.startswith('field:')]
def predict(form):
    # Zap's published serialization keys, with only our privacy-filtered features.
    ids=[tok.cls_token_id]+tok('[HEAD] '+form['context'],add_special_tokens=False)['input_ids']; pos=[]
    for f in form['fields']:
        pos.append(len(ids))
        text='[FLD] [TYPE] '+f['type']
        if f['autocomplete']: text+=' [AC] '+f['autocomplete']
        if f['hint']: text+=' [LBL] '+f['hint']
        ids+=tok(text,add_special_tokens=False)['input_ids']
    ids.append(tok.sep_token_id)
    if len(ids)>512: raise ValueError('Zap comparison requires windowing above 512 tokens')
    with torch.no_grad(): logits=model(input_ids=torch.tensor([ids]),attention_mask=torch.ones((1,len(ids)),dtype=torch.long)).logits[0]
    purpose=labels[form_ids[int(logits[0,form_ids].argmax())]][5:]
    fields=[labels[field_ids[int(logits[posi,field_ids].argmax())]][6:] for posi in pos]
    return purpose if purpose in FORMS else 'other',[x if x in FIELDS else 'other' for x in fields]
rows=load(args.data)
for _ in range(5): predict(rows[0]['form'])
report={'revision':args.revision,'parameters':sum(p.numel() for p in model.parameters()),'scope':'restricted safe features, synthetic test, PyTorch CPU; not official Zap extraction benchmark','result':evaluate(rows,predict)}
Path(args.output).write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
