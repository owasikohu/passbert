"""Build a self-contained Firefox evaluation extension; never include training data."""
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--model',default='artifacts/kaggle-v2-output/model');p.add_argument('--output',default='artifacts/firefox-extension');args=p.parse_args()
root=Path(__file__).resolve().parents[1];out=root/args.output;source=root/args.model
required=['tokenizer.json','model.int8.onnx']
for name in required:
    if not (source/name).is_file():p.error(f'Missing model artifact: {source/name}')
ort=root/'node_modules/onnxruntime-web'
if not (ort/'dist/ort.wasm.min.mjs').exists():p.error('Run npm ci first')
out.mkdir(parents=True,exist_ok=True)
for f in (root/'extension/firefox').iterdir():
    if f.is_file():shutil.copy2(f,out/f.name)
shutil.copytree(root/'web',out/'web',dirs_exist_ok=True)
(out/'evaluation.mjs').write_text((out/'evaluation.mjs').read_text().replace('../../web/policy.mjs','./web/policy.mjs'))
(out/'model').mkdir(exist_ok=True);(out/'vendor').mkdir(exist_ok=True)
for name in required:shutil.copy2(source/name,out/'model'/name)
metadata={'name':'passbert-tinybert','artifact_source':str(Path(args.model)),'sha256':{name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in required},'runtime':'onnxruntime-web@1.23.2','backend':'wasm','threads':1,'training_data':'synthetic-v2; real-world accuracy unverified'}
(out/'model/metadata.json').write_text(json.dumps(metadata,indent=2))
for name in ['ort.wasm.min.mjs','ort-wasm-simd-threaded.mjs','ort-wasm-simd-threaded.wasm']:
    shutil.copy2(ort/'dist'/name,out/'vendor'/name)
shutil.copy2(root/'third_party/ONNX-RUNTIME-LICENSE',out/'vendor/ONNX-RUNTIME-LICENSE')
shutil.copy2(root/'third_party/ONNX-RUNTIME-NOTICES',out/'vendor/ONNX-RUNTIME-NOTICES')
shutil.copy2(root/'LICENSE',out/'LICENSE')
policy=(root/'web/policy.mjs').read_text().replace('export const','const')
extract=(root/'web/extract.mjs').read_text();extract='\n'.join(line for line in extract.splitlines() if not line.startswith('import ')).replace('export function','function').replace('export const','const')
capture='''\nconst start=performance.now();const elements=[];
const forms=extract(document,{onField:el=>elements.push(el)});let offset=0;
const groups=forms.map(f=>{const refs=elements.slice(offset,offset+f.fields.length);offset+=f.fields.length;return refs;});
const key=crypto.randomUUID();
globalThis.__passbertEvaluation?.overlay?.remove();
globalThis.__passbertEvaluation={key,groups};
return {snapshot_key:key,hostname:location.hostname,forms,visibility:groups.map(fields=>fields.map(el=>{const r=el.getBoundingClientRect();const style=getComputedStyle(el);return !!(r.width&&r.height&&style.visibility!=='hidden'&&style.display!=='none');})),extraction_ms:performance.now()-start};
'''
(out/'capture.js').write_text('(()=>{\n'+policy+'\n'+extract+'\n'+capture+'\n})()\n')
# Explicit allowlist avoids shipping stale files or arbitrary source/data in the XPI.
files=[*(out/f.name for f in (root/'extension/firefox').iterdir() if f.is_file()),out/'capture.js',out/'LICENSE',*(out/'web'/f for f in ['infer.mjs','extract.mjs','policy.mjs','decision.mjs']),*(out/'vendor'/f for f in ['ort.wasm.min.mjs','ort-wasm-simd-threaded.mjs','ort-wasm-simd-threaded.wasm','ONNX-RUNTIME-LICENSE','ONNX-RUNTIME-NOTICES']),*(out/'model'/f for f in [*required,'metadata.json'])]
xpi=out.parent/'passbert-firefox-eval.xpi'
with zipfile.ZipFile(xpi,'w',zipfile.ZIP_DEFLATED) as z:
    for file in sorted(files):z.write(file,file.relative_to(out))
print(json.dumps({'extension':str(out),'xpi':str(xpi),'bytes':xpi.stat().st_size,'model':metadata},indent=2))
