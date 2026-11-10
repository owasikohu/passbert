"""Watch one authorized Kaggle job, then collect and assess it; never launch another GPU run."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime,timezone
from passbert.kaggle_watch import kernel_status

p=argparse.ArgumentParser();p.add_argument('--kernel',default='owasikohu/passbert-blind-review-qwen38-v1');p.add_argument('--root',default='artifacts/blind-review');p.add_argument('--timeout',type=int,default=21600);p.add_argument('--interval',type=int,default=60);args=p.parse_args()
root=Path(args.root);root.mkdir(parents=True,exist_ok=True);started=time.monotonic()
cli=Path(sys.executable).with_name('kaggle');cli=str(cli) if cli.exists() else shutil.which('kaggle')
def state(status,**extra):
 value={'kernel':args.kernel,'status':status,'updated_at':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':round(time.monotonic()-started),'gold_labels':0,'training_promotions':0,**extra}
 (root/'watch-status.json').write_text(json.dumps(value,indent=2));print(json.dumps(value),flush=True)
try:
 while time.monotonic()-started<args.timeout:
    try:current=kernel_status(cli,args.kernel,timeout=45)
    except subprocess.TimeoutExpired:
        state('poll_timeout');time.sleep(args.interval);continue
    state(current)
    if current=='complete':
        destination=root/'output'
        for attempt in range(4):
            try:result=subprocess.run([cli,'kernels','output',args.kernel,'-p',str(destination)],timeout=300)
            except subprocess.TimeoutExpired:result=subprocess.CompletedProcess([],1)
            if result.returncode==0:break
            if attempt==3:raise RuntimeError('Output retrieval failed')
            time.sleep(30)
        metadata=json.loads((destination/'review-output/metadata.json').read_text())
        expected=hashlib.sha256((root/'blind-local.jsonl').read_bytes()).hexdigest()
        if metadata.get('records')!=len((root/'blind-local.jsonl').read_text().splitlines()):raise RuntimeError('Incomplete reviewer output')
        if metadata['input_sha256']!=expected:raise RuntimeError('Blind input hash mismatch')
        subprocess.run([sys.executable,'-m','scripts.summarize_review','--root',str(root),'--reviews',str(destination/'review-output/reviews.jsonl')],check=True)
        assessment=json.loads((root/'assessment.json').read_text())
        passed=assessment['controls']['exact']==assessment['controls']['total'] and assessment['counts'].get('missing_or_invalid',0)==0
        state('assessed' if passed else 'assessed_needs_attention',controls=assessment['controls']['exact'],control_total=assessment['controls']['total'],counts=assessment['counts']);break
    if any(word in current for word in ['error','fail','cancel']):raise RuntimeError('Kaggle job ended with '+current)
    time.sleep(args.interval)
 else:state('watch_timeout');raise SystemExit(2)
except Exception as error:
 state('watch_error',error_type=type(error).__name__);raise
