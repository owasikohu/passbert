"""Bundle only allowlisted project sources, submit private T4 kernel, collect outputs."""
import argparse
import base64
import io
import json
from pathlib import Path
import subprocess
import zipfile

p=argparse.ArgumentParser(); p.add_argument('action',choices=['prepare','push','status','output']); p.add_argument('--owner',required=True); p.add_argument('--slug',default='passbert-tinybert-v2'); p.add_argument('--output-dir',default='artifacts/kaggle-v2-output'); args=p.parse_args()
if not args.owner.replace('-','').replace('_','').isalnum(): p.error('Invalid owner')
kernel=f'{args.owner}/{args.slug}'; root=Path('artifacts/kaggle'); root.mkdir(parents=True,exist_ok=True)
if args.action=='prepare':
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        for path in [Path('pyproject.toml'),Path('LICENSE'),*Path('passbert').glob('*.py')]: z.write(path,str(path))
    payload=base64.b64encode(buf.getvalue()).decode()
    code=f'''import base64, io, zipfile, subprocess, sys, os
from pathlib import Path
os.chdir('/kaggle/working')
zipfile.ZipFile(io.BytesIO(base64.b64decode({payload!r}))).extractall('source')
subprocess.run([sys.executable,'-m','pip','install','./source'],check=True)
import torch
assert torch.cuda.is_available(), 'GPU required'
assert 'T4' in torch.cuda.get_device_name(0), 'Requested T4 was not allocated'
subprocess.run([sys.executable,'-m','passbert.train','--generate','--generator','v2','--epochs','12','--output','model'],check=True)
Path('hardware.json').write_text(__import__('json').dumps({{'gpu':torch.cuda.get_device_name(0),'torch':torch.__version__}}))
'''
    (root/'train.py').write_text(code)
    (root/'kernel-metadata.json').write_text(json.dumps({'id':kernel,'title':args.slug,'code_file':'train.py','language':'python','kernel_type':'script','is_private':True,'enable_gpu':True,'enable_internet':True,'dataset_sources':[],'competition_sources':[],'kernel_sources':[]},indent=2))
else:
    commands={'push':['kernels','push','-p',str(root),'--accelerator','NvidiaTeslaT4'],'status':['kernels','status',kernel],'output':['kernels','output',kernel,'-p',args.output_dir]}
    subprocess.run(['kaggle',*commands[args.action]],check=True)
