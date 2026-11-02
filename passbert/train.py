import argparse
import json
import random
import time
from pathlib import Path
import numpy as np
import torch
from tokenizers import Tokenizer, models, trainers, pre_tokenizers, decoders
from transformers import BertConfig, BertForTokenClassification
from passbert.data import FIELDS, FORMS, serialize, load, generate
from passbert.metrics import score

LABELS = ['form:'+x for x in FORMS] + ['field:'+x for x in FIELDS]

def encode(tok, row):
    ids = tok.encode(serialize(row['form'])).ids
    if len(ids) > 256:
        raise ValueError('Form exceeds 256 tokens; windowing required, never silently truncate fields')
    pos = [i for i,t in enumerate(ids) if t == tok.token_to_id('[FLD]')]
    assert len(pos) == len(row['field_labels'])
    labels = [-100]*len(ids); labels[0] = FORMS.index(row['form_label'])
    for p, label in zip(pos,row['field_labels']): labels[p] = len(FORMS)+FIELDS.index(label)
    return ids, labels

def batch(tok, rows, device):
    enc = [encode(tok,r) for r in rows]; length = max(len(x[0]) for x in enc)
    ids = torch.tensor([a+[0]*(length-len(a)) for a,b in enc],device=device)
    labels = torch.tensor([b+[-100]*(length-len(b)) for a,b in enc],device=device)
    return {'input_ids':ids,'attention_mask':(ids!=0).long(),'labels':labels}

def heuristic(form):
    text=form['context']; fields=[]
    for f in form['fields']:
        h=f['hint']; ac=f['autocomplete'].split()
        label=next((x for x in ac if x in FIELDS),None)
        if not label:
            if 'otp' in h or 'code' in h or 'コード' in h: label='one-time-code'
            elif f['type']=='password' or 'password' in h or 'パスワード' in h:
                label='new-password' if any(x in text+h for x in ['register','sign up','new','confirm','登録','新規','再設定']) else 'current-password'
            elif f['type']=='email' or 'email' in h or 'メール' in h: label='email'
            elif 'user' in h or 'ユーザー' in h: label='username'
            elif 'search' in h or '検索' in h: label='search'
            else: label='other'
        fields.append(label)
    purpose='other'
    for label, words in [('login',['sign in','login','ログイン']),('signup',['sign up','register','登録']),('password-recovery',['reset','recover','再設定']),('otp',['verification','認証']),('search',['search','検索'])]:
        if any(x in text for x in words): purpose=label; break
    return purpose, fields

def evaluate(rows, predict):
    ft=[]; fp=[]; yt=[]; yp=[]; times=[]
    for row in rows:
        start=time.perf_counter(); p,fields=predict(row['form']); times.append((time.perf_counter()-start)*1000)
        assert len(fields)==len(row['field_labels'])
        yt.append(row['form_label']); yp.append(p); ft.extend(row['field_labels']); fp.extend(fields)
    return {'form':score(yt,yp,FORMS),'field':score(ft,fp,FIELDS),'latency_ms':{'p50':float(np.percentile(times,50)),'p95':float(np.percentile(times,95))},'forms':len(rows)}

def run(args):
    torch.set_num_threads(2); torch.manual_seed(42); random.seed(42); np.random.seed(42)
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    if args.generate: generate(args.data)
    train=load(Path(args.data)/'train.jsonl'); val=load(Path(args.data)/'val.jsonl'); test=load(Path(args.data)/'test.jsonl')
    for key in ['site_id','signature','template_family']:
        sets=[{r[key] for r in rows} for rows in [train,val,test]]
        assert all(not sets[i]&sets[j] for i in range(3) for j in range(i))
    tok=Tokenizer(models.WordPiece(unk_token='[UNK]')); tok.pre_tokenizer=pre_tokenizers.BertPreTokenizer(); tok.decoder=decoders.WordPiece()
    tok.train_from_iterator((serialize(r['form']) for r in train),trainers.WordPieceTrainer(vocab_size=4096,special_tokens=['[PAD]','[UNK]','[CLS]','[SEP]','[MASK]','[FLD]']))
    # Fixed capacity keeps architecture 1–2M even for a small smoke corpus.
    tok.save(str(out/'tokenizer.json'))
    config=BertConfig(vocab_size=4096,hidden_size=128,num_hidden_layers=4,num_attention_heads=4,intermediate_size=512,max_position_embeddings=256,num_labels=len(LABELS),id2label=dict(enumerate(LABELS)),label2id={x:i for i,x in enumerate(LABELS)},pad_token_id=0)
    model=BertForTokenClassification(config); device='cuda' if torch.cuda.is_available() else 'cpu'; model.to(device)
    params=sum(p.numel() for p in model.parameters()); assert 1_000_000<=params<=2_000_000
    optim=torch.optim.AdamW(model.parameters(),lr=5e-4); best=-1; history=[]
    def predict(form):
        row={'form':form,'form_label':'other','field_labels':['other']*len(form['fields'])}
        x=batch(tok,[row],device); x.pop('labels')
        with torch.no_grad(): logits=model(**x).logits[0].cpu()
        positions=(x['input_ids'][0].cpu()==tok.token_to_id('[FLD]')).nonzero().flatten().tolist()
        return FORMS[logits[0,:len(FORMS)].argmax()], [FIELDS[logits[p,len(FORMS):].argmax()] for p in positions]
    for epoch in range(args.epochs):
        model.train(); random.shuffle(train); losses=[]
        for start in range(0,len(train),32):
            optim.zero_grad(); loss=model(**batch(tok,train[start:start+32],device)).loss
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),1); optim.step(); losses.append(loss.item())
        model.eval(); metrics=evaluate(val,predict); metric=(metrics['form']['macro_f1']+metrics['field']['macro_f1'])/2
        history.append({'epoch':epoch+1,'loss':sum(losses)/len(losses),'validation_macro_f1':metric})
        print(json.dumps(history[-1]),flush=True)
        if metric>best: best=metric; model.save_pretrained(out)
    model=BertForTokenClassification.from_pretrained(out).to(device).eval()
    # Test is consulted only after validation-based checkpoint selection.
    report={'device':device,'parameters':params,'vocabulary_used':tok.get_vocab_size(),'history':history,'tinybert':evaluate(test,predict),'heuristic':evaluate(test,heuristic),'scope':'synthetic smoke test, not real-world accuracy','zap':{'status':'not_run'}}
    model.cpu(); device='cpu'
    sample=batch(tok,test[:1],device); sample.pop('labels')
    class Export(torch.nn.Module):
        def __init__(self,m): super().__init__(); self.m=m
        def forward(self,input_ids,attention_mask): return self.m(input_ids=input_ids,attention_mask=attention_mask).logits
    torch.onnx.export(Export(model),(sample['input_ids'],sample['attention_mask']),str(out/'model.onnx'),input_names=['input_ids','attention_mask'],output_names=['logits'],dynamic_axes={'input_ids':{0:'batch',1:'sequence'},'attention_mask':{0:'batch',1:'sequence'},'logits':{0:'batch',1:'sequence'}},opset_version=17,dynamo=False)
    from onnxruntime.quantization import quantize_dynamic, QuantType
    import onnxruntime as ort
    quantize_dynamic(str(out/'model.onnx'),str(out/'model.int8.onnx'),weight_type=QuantType.QInt8)
    options=ort.SessionOptions(); options.intra_op_num_threads=2
    reference=model(**sample).logits.detach().numpy(); report['onnx']={}
    for name in ['model.onnx','model.int8.onnx']:
        session=ort.InferenceSession(str(out/name),sess_options=options,providers=['CPUExecutionProvider'])
        def onnx_predict(form):
            row={'form':form,'form_label':'other','field_labels':['other']*len(form['fields'])}; x=batch(tok,[row],'cpu'); x.pop('labels')
            logits=session.run(None,{k:v.numpy() for k,v in x.items()})[0][0]
            pos=(x['input_ids'][0]==tok.token_to_id('[FLD]')).nonzero().flatten().tolist()
            return FORMS[int(logits[0,:len(FORMS)].argmax())],[FIELDS[int(logits[p,len(FORMS):].argmax())] for p in pos]
        for _ in range(5): onnx_predict(test[0]['form'])
        report['onnx'][name]={'bytes':(out/name).stat().st_size,'test':evaluate(test,onnx_predict),'sample_max_abs_error':float(np.abs(session.run(None,{k:v.numpy() for k,v in sample.items()})[0]-reference).max())}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:report[k] for k in ['device','parameters','vocabulary_used']},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--data',default='artifacts/data'); p.add_argument('--output',default='artifacts/smoke'); p.add_argument('--epochs',type=int,default=8); p.add_argument('--generate',action='store_true'); run(p.parse_args())
