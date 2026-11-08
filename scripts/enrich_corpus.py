"""Replay archive members to add expanded semantic descriptors; never persist raw HTML/values."""
import argparse
import json
import re
import sqlite3
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
from warcio.archiveiterator import ArchiveIterator
from selectolax.lexbor import LexborHTMLParser
from passbert.data import extract,signature
from passbert.fast_extract import extract_fast


def enrich(row):
    source=row['source_ref'];path=source['warc'];offset=int(source['offset'])
    if not path.startswith('crawl-data/CC-MAIN-') or '..' in path or offset<0:return row,'invalid_locator'
    try:
        with requests.get('https://data.commoncrawl.org/'+path,headers={'Range':f'bytes={offset}-{offset+2*1024*1024-1}'},stream=True,timeout=(15,45),allow_redirects=False) as response:
            if response.status_code!=206:return row,'http_'+str(response.status_code)
            record=next(iter(ArchiveIterator(response.raw)))
            if record.rec_type!='response' or not record.http_headers:return row,'wrong_record'
            body=record.content_stream().read(1_000_001)
            if len(body)>1_000_000:return row,'oversize'
            header=record.http_headers.get_header('Content-Type','');match=re.search(r'charset\s*=\s*["\x27]?([\w-]+)',header,re.I)
            try:html=body.decode(match[1] if match else 'utf-8',errors='replace')
            except LookupError:html=body.decode('utf-8',errors='replace')
        views=[]
        if 'native' in row.get('extraction',''):forms,views=extract_fast(html)
        else:forms=extract(LexborHTMLParser(html).html,_parser='lxml',_annotation_views=views)
        index=source['form_index']
        if index>=len(forms) or signature(forms[index])!=row['signature']:return row,'replay_mismatch'
        row['annotation_view']=views[index];row['annotation_policy']='semantic-annotation-v2'
        return row,'enriched'
    except Exception as error:return row,'error:'+type(error).__name__


def main():
 p=argparse.ArgumentParser();p.add_argument('--root',default='artifacts/corpus-10k');p.add_argument('--workers',type=int,default=4);p.add_argument('--limit',type=int,default=10000);args=p.parse_args()
 root=Path(args.root);db=sqlite3.connect(root/'corpus.sqlite',timeout=60)
 rows=[json.loads(value) for value, in db.execute('SELECT row_json FROM forms')];rows=[r for r in rows if 'annotation_view' not in r][:args.limit];counts=Counter()
 with ThreadPoolExecutor(max_workers=args.workers) as pool:
    for row,status in pool.map(enrich,rows):
        counts[status]+=1
        if status=='enriched':db.execute('UPDATE forms SET row_json=? WHERE fingerprint=?',(json.dumps(row,ensure_ascii=False),row['template_family']));db.commit()
        if sum(counts.values())%100==0:print(json.dumps(dict(counts)),flush=True)
 (root/'enrichment-report.json').write_text(json.dumps(dict(counts),indent=2));print(json.dumps(dict(counts)),flush=True)
 from passbert.corpus import Corpus
 exported=Corpus(root/'corpus.sqlite').export(root)
 manifest=root/'manifest.json'
 old=json.loads(manifest.read_text()) if manifest.exists() else {}
 manifest.write_text(json.dumps({**old,**exported},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
