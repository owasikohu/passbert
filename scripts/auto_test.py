"""One command for local checks, packaged Firefox smoke, and optional opt-in live audit."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--model',default='artifacts/kaggle-v2-output/model');p.add_argument('--firefox',default='artifacts/firefox-runtime/firefox/firefox');p.add_argument('--live',action='store_true');args=p.parse_args()
root=Path(__file__).resolve().parents[1];steps=[];out=root/'artifacts/automation';out.mkdir(parents=True,exist_ok=True)
def run(name,command):
 start=time.perf_counter()
 with (out/f'{name}.log').open('w') as log:result=subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT)
 steps.append({'name':name,'passed':result.returncode==0,'seconds':round(time.perf_counter()-start,2),'log':str(out/f'{name}.log')});print(json.dumps(steps[-1]),flush=True)
 (out/'report.json').write_text(json.dumps(steps,indent=2))
 if result.returncode:raise SystemExit(result.returncode)
run('python',[sys.executable,'-m','unittest','discover','-s','tests','-v'])
run('policy',[sys.executable,'-m','scripts.sync_policy','--check'])
run('build',[sys.executable,'scripts/build_firefox.py','--model',args.model])
run('parity',[sys.executable,'-m','scripts.browser_parity','--model',args.model])
run('browser',['node','tests/browser.test.mjs'])
run('extension',['node','tests/extension.test.mjs'])
run('lint',['node_modules/.bin/web-ext','lint','--source-dir','artifacts/firefox-extension','--no-config-discovery'])
run('firefox',[sys.executable,'scripts/firefox_smoke.py','--firefox',args.firefox])
run('firefox-auto',[sys.executable,'scripts/firefox_smoke.py','--firefox',args.firefox,'--automatic'])
run('firefox-long',[sys.executable,'scripts/firefox_smoke.py','--firefox',args.firefox,'--automatic','--long'])
run('robustness',[sys.executable,'-m','scripts.audit_fixtures','--model',args.model,'--output',str(out/'robustness.json'),'--require-raw','10','--require-guarded','12'])
if args.live:run('live',[sys.executable,'-m','scripts.audit_live','--model',args.model,'--firefox',args.firefox,'--output',str(out/'live.json')])
