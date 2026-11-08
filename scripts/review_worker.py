"""Pinned llama.cpp/GGUF review on two T4s; knows no Zap outputs or control answers."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
from passbert.review import TEACHER,REVISION,SYSTEM,FORM_LABELS,FIELD_LABELS,messages,parse_labels


def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def download(url,path,expected_hash,expected_size=None):
    for attempt in range(4):
        offset=path.stat().st_size if path.exists() else 0
        if expected_size and offset==expected_size:break
        try:
            with requests.get(url,headers={'Range':f'bytes={offset}-'} if offset else {},stream=True,timeout=(30,120)) as response:
                response.raise_for_status()
                mode='ab' if offset and response.status_code==206 else 'wb'
                with path.open(mode) as f:
                    for chunk in response.iter_content(8*1024*1024):f.write(chunk)
            break
        except requests.RequestException:
            if attempt==3:raise
            time.sleep(2**attempt)
    if expected_size and path.stat().st_size!=expected_size:raise ValueError('Unexpected download size')
    if sha256(path)!=expected_hash:raise ValueError('Download SHA-256 mismatch')


def schema(count):return {'type':'object','properties':{'form_label':{'type':'string','enum':FORM_LABELS},'field_labels':{'type':'array','minItems':count,'maxItems':count,'items':{'type':'string','enum':FIELD_LABELS}}},'required':['form_label','field_labels'],'additionalProperties':False}


def main():
 p=argparse.ArgumentParser();p.add_argument('--input',default='blind.jsonl');p.add_argument('--config',default='qwen-config.json');p.add_argument('--output',default='review-output');args=p.parse_args()
 out=Path(args.output);out.mkdir(parents=True,exist_ok=True);config=json.loads(Path(args.config).read_text());started=time.monotonic()
 gpus=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader,nounits'],text=True).strip().splitlines()
 assert len(gpus)>=2 and all('T4' in gpu for gpu in gpus[:2]),'Two T4 GPUs required'
 metadata={'model':config['model'],'base_revision_reference':config['base_revision_reference'],'quant_repo':config['quant_repo'],'revision':config['quant_revision'],'quant_file':config['quant_file'],'quant_sha256':config['quant_sha256'],'llama_release':config['llama_release'],'gpus':gpus,'input_sha256':sha256(Path(args.input)),'prompt_sha256':hashlib.sha256(SYSTEM.encode()).hexdigest(),'reasoning_effort':'medium','reasoning_budget':512,'max_tokens':896,'temperature':0,'seed':20261109,'parallel':4,'blind':True,'gold_labels':0}
 (out/'metadata.json').write_text(json.dumps(metadata,indent=2))
 with tempfile.TemporaryDirectory(prefix='passbert-review-') as folder:
    temp=Path(folder)
    if shutil.disk_usage(temp).free<config['quant_bytes']+3*1024**3:raise RuntimeError('Insufficient temporary disk for the Q6 model')
    for asset in config['assets']:
        path=temp/asset['name'];print('Downloading runtime',asset['name'],flush=True);download(asset['url'],path,asset['digest'].split(':')[1])
        with tarfile.open(path) as archive:archive.extractall(temp/'runtime',filter='data')
        path.unlink()
    model=temp/config['quant_file'];print('Downloading Q6 teacher',config['quant_file'],flush=True)
    download(f"https://huggingface.co/{config['quant_repo']}/resolve/{config['quant_revision']}/{config['quant_file']}",model,config['quant_sha256'],config['quant_bytes'])
    binaries=list((temp/'runtime').rglob('llama-server'))
    if len(binaries)!=1:raise RuntimeError('Expected exactly one llama-server')
    binary=binaries[0];environment=dict(os.environ);library_dirs={str(p.parent) for p in (temp/'runtime').rglob('*.so*')}
    environment['LD_LIBRARY_PATH']=':'.join(sorted(library_dirs))+':'+environment.get('LD_LIBRARY_PATH','')
    command=[str(binary),'-m',str(model),'--host','127.0.0.1','--port','8080','--gpu-layers','all','--split-mode','layer','--tensor-split','1,1','--fit','off','--ctx-size','16384','--parallel','4','--batch-size','512','--ubatch-size','128','--threads','4','--jinja','--reasoning','on','--reasoning-format','deepseek','--reasoning-budget','512','--alias',TEACHER]
    server_log=(out/'server.log').open('w');server=subprocess.Popen(command,env=environment,stdout=server_log,stderr=subprocess.STDOUT)
    try:
        ready=False
        for _ in range(600):
            if server.poll() is not None:raise RuntimeError('llama-server exited; inspect server.log')
            try:
                if requests.get('http://127.0.0.1:8080/health',timeout=2).status_code==200:ready=True;break
            except requests.RequestException:pass
            time.sleep(2)
        if not ready:raise RuntimeError('Model initialization timed out')
        metadata['load_seconds']=round(time.monotonic()-started,2);print('Teacher ready',json.dumps(metadata),flush=True)
        rows=[json.loads(line) for line in Path(args.input).read_text().splitlines() if line]
        def review(request):
            record={'record_id':request['record_id'],'reviewer':config['model'],'revision':config['quant_revision'],'quant_file':config['quant_file'],'kind':request['kind'],'verified':False,'training_eligible':False}
            payload={'model':TEACHER,'messages':messages(request),'temperature':0,'seed':20261109,'max_tokens':896,'reasoning_effort':'medium','response_format':{'type':'json_object','schema':schema(len(request['form']['fields']))}}
            try:
                result=requests.post('http://127.0.0.1:8080/v1/chat/completions',json=payload,timeout=600);result.raise_for_status();data=result.json();text=data['choices'][0]['message'].get('content') or ''
                record.update(parse_labels(text,len(request['form']['fields'])));record['status']='valid';record['completion_sha256']=hashlib.sha256(text.encode()).hexdigest();record['usage']=data.get('usage',{})
            except ValueError as error:record.update({'status':'invalid','error':str(error) if str(error) in ['invalid_json','invalid_schema','invalid_form_label','field_alignment_mismatch','invalid_field_label'] else 'invalid_response'})
            except Exception as error:record.update({'status':'invalid','error':type(error).__name__})
            return record
        with (out/'reviews.jsonl').open('w') as f,ThreadPoolExecutor(max_workers=4) as pool:
            for i,record in enumerate(pool.map(review,rows),1):
                f.write(json.dumps(record,ensure_ascii=False)+'\n');f.flush();print(json.dumps({'completed':i,'total':len(rows),'status':record['status'],'seconds':round(time.monotonic()-started)}),flush=True)
        metadata['records']=len(rows);metadata['elapsed_seconds']=round(time.monotonic()-started,2)
        (out/'metadata.json').write_text(json.dumps(metadata,indent=2))
    finally:
        server.terminate()
        try:server.wait(timeout=20)
        except subprocess.TimeoutExpired:server.kill();server.wait()
        server_log.close()
if __name__=='__main__':main()
