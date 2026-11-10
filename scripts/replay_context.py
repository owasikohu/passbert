"""Re-extract the same train-only reviewed records with v3 semantic context. No labels are used."""
import argparse
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
from warcio.archiveiterator import ArchiveIterator
from passbert.data import signature
from passbert.fast_extract import extract_fast
from passbert.context_v3 import render,VERSION
from passbert.review import valid_view


def replay(pair):
 request,row=pair;source=row['source_ref'];offset=int(source['offset']);path=source['warc']
 if not path.startswith('crawl-data/CC-MAIN-') or '..' in path or offset<0:return request,None,'invalid_locator'
 for attempt in range(3):
  stage='download'
  try:
   with requests.get('https://data.commoncrawl.org/'+path,headers={'Range':f'bytes={offset}-{offset+2*1024*1024-1}'},stream=True,timeout=(15,45),allow_redirects=False) as response:
    if response.status_code!=206:raise ValueError('archive_http_'+str(response.status_code))
    stage='warc'
    record=next(iter(ArchiveIterator(response.raw)))
    if record.rec_type!='response' or not record.http_headers:raise ValueError('wrong_record')
    body=record.content_stream().read(1_000_001)
    if len(body)>1_000_000:raise ValueError('oversize')
    match=re.search(r'charset\s*=\s*["\x27]?([\w-]+)',record.http_headers.get_header('Content-Type',''),re.I)
    try:html=body.decode(match[1] if match else 'utf-8',errors='replace')
    except LookupError:html=body.decode('utf-8',errors='replace')
   stage='extract'
   forms,views=extract_fast(html,annotation_builder=render);index=source['form_index']
   if index>=len(forms) or signature(forms[index])!=row['signature']:return request,None,'replay_mismatch'
   view=views[index]
   if not valid_view(view,VERSION) or len(view['fields'])!=len(request['form']['fields']):return request,None,'unsafe_or_misaligned_view'
   overlay={'record_id':row['record_id'],'split':'train','evaluation_only':False,'source_signature':row['signature'],'annotation_view':view,'annotation_policy':VERSION}
   return {**request,'form':view,'annotation_policy':VERSION},overlay,'ok'
  except Exception as error:
   if attempt==2:
    code=str(error) if isinstance(error,ValueError) and str(error).startswith('archive_http_') else type(error).__name__
    return request,None,'error:'+stage+':'+code
   time.sleep(2**attempt)


def main():
 p=argparse.ArgumentParser();p.add_argument('--requests',default='artifacts/corpus-10k/label-pilot/blind-review-requests.jsonl');p.add_argument('--train',default='artifacts/corpus-10k/train.jsonl');p.add_argument('--output',default='artifacts/context-review-v3');args=p.parse_args()
 train={r['record_id']:r for r in (json.loads(l) for l in Path(args.train).read_text().splitlines())};old=[json.loads(l) for l in Path(args.requests).read_text().splitlines()];pairs=[]
 for r in old:
  row=train[r['record_id']]
  if row['split']!='train' or row.get('evaluation_only'):raise ValueError('Reserved record')
  if r['form']!=row['annotation_view']:raise ValueError('Baseline view changed')
  pairs.append((r,row))
 root=Path(args.output);root.mkdir(parents=True,exist_ok=True);new=[];overlays=[];statuses={};details=[]
 with ThreadPoolExecutor(max_workers=4) as pool:
  for i,(request,overlay,status) in enumerate(pool.map(replay,pairs),1):
   statuses[status]=statuses.get(status,0)+1
   if overlay is not None:new.append(request);overlays.append(overlay)
   details.append({'record_id':request['record_id'],'status':status})
   if i%10==0:print(json.dumps({'processed':i,'statuses':statuses}),flush=True)
 (root/'requests.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in new));(root/'overlays.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in overlays))
 old_fields=[f for r in old for f in r['form']['fields']];new_fields=[f for r in new for f in r['form']['fields']]
 report={'policy':VERSION,'requested':len(old),'successful':len(new),'statuses':statuses,'baseline_requests_sha256':hashlib.sha256(Path(args.requests).read_bytes()).hexdigest(),'empty_field_hints_before':sum(not f['hint'] for f in old_fields),'empty_field_hints_after':sum(not f['hint'] for f in new_fields),'fields_before':len(old_fields),'fields_after':len(new_fields),'raw_html_saved':False,'baseline_corpus_modified':False,'details':details}
 (root/'replay-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='details'},ensure_ascii=False))
 if len(new)!=len(old):raise SystemExit(2)
if __name__=='__main__':main()
