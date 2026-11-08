"""Bundle only allowlisted blind features and review code into a private Kaggle kernel."""
import argparse
import base64
import io
import json
import zipfile
from pathlib import Path
from passbert.review import blind_payload

p=argparse.ArgumentParser();p.add_argument('--owner',default='owasikohu');p.add_argument('--slug',default='passbert-blind-review-qwen38-v1');p.add_argument('--teacher-config',default='configs/review-qwen38-q6.json');args=p.parse_args()
source=Path('artifacts/corpus-10k');train={r['record_id']:r for r in (json.loads(l) for l in (source/'train.jsonl').read_text().splitlines())}
requests=[json.loads(line) for line in (source/'label-pilot/blind-review-requests.jsonl').read_text().splitlines()]
rows=[blind_payload(r,train[r['record_id']]) for r in requests]
# Known control answers stay local; the GPU payload contains only their features.
controls=[
 ('login-en',{'context':'sign in','fields':[{'type':'text','hint':'username','autocomplete':'username'},{'type':'password','hint':'current password','autocomplete':'current-password'}]},'login',['username','current-password']),
 ('signup-ja',{'context':'新規 登録','fields':[{'type':'email','hint':'メール','autocomplete':'email'},{'type':'password','hint':'新規 パスワード','autocomplete':'new-password'}]},'signup',['email','new-password']),
 ('otp-ja',{'context':'認証 コード','fields':[{'type':'text','hint':'認証 コード','autocomplete':'one-time-code'}]},'otp',['one-time-code']),
 ('search-en',{'context':'search','fields':[{'type':'search','hint':'search','autocomplete':''}]},'search',['search']),
 ('ambiguous-email',{'context':'','fields':[{'type':'email','hint':'email','autocomplete':''}]},'unreviewable',['email']),
 ('ambiguous-text',{'context':'','fields':[{'type':'text','hint':'','autocomplete':''}]},'unreviewable',['unreviewable']),
 ('ambiguous-password',{'context':'','fields':[{'type':'password','hint':'','autocomplete':''}]},'unreviewable',['unreviewable']),
 ('reset-en',{'context':'reset password','fields':[{'type':'email','hint':'email','autocomplete':'email'}]},'password-recovery',['email']),
]
answers=[]
for name,form,purpose,fields in controls:
    record_id='control-'+name;rows.append({'record_id':record_id,'language':'ja' if name.endswith('-ja') else 'en','form':form,'kind':'control'});answers.append({'record_id':record_id,'form_label':purpose,'field_labels':fields})
import random
random.Random(20261109).shuffle(rows)
root=Path('artifacts/blind-review');root.mkdir(parents=True,exist_ok=True);(root/'controls-local.json').write_text(json.dumps(answers,ensure_ascii=False,indent=2))
(root/'blind-local.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
buf=io.BytesIO()
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
    for path in ['passbert/__init__.py','passbert/data.py','passbert/annotation.py','passbert/review.py','scripts/review_worker.py']:z.write(path,path)
    z.write(args.teacher_config,'qwen-config.json')
    z.writestr('blind.jsonl',''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
payload=base64.b64encode(buf.getvalue()).decode()
code=f'''import os,sys,subprocess,zipfile,base64,io
from pathlib import Path
os.chdir('/kaggle/working')
subprocess.run([sys.executable,'-m','pip','install','requests','beautifulsoup4','html5lib'],check=True)
zipfile.ZipFile(io.BytesIO(base64.b64decode({payload!r}))).extractall('.')
subprocess.run([sys.executable,'-m','scripts.review_worker'],check=True)
'''
job=root/'kernel';job.mkdir(exist_ok=True);(job/'review.py').write_text(code)
(job/'kernel-metadata.json').write_text(json.dumps({'id':args.owner+'/'+args.slug,'title':args.slug,'code_file':'review.py','language':'python','kernel_type':'script','is_private':True,'enable_gpu':True,'enable_internet':True,'dataset_sources':[],'competition_sources':[],'kernel_sources':[]},indent=2))
print(json.dumps({'corpus_requests':len(requests),'controls':len(controls),'kernel':str(job),'blind':True,'teacher_predictions_uploaded':False},indent=2))
