"""Stream bounded WARC shards; persist only allowlisted form features, never raw pages/URLs/values."""
import argparse
import gzip
import io
import json
import random
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import requests
from warcio.archiveiterator import ArchiveIterator
from selectolax.lexbor import LexborHTMLParser
from passbert.data import extract,signature
from passbert.fast_extract import extract_fast
from passbert.corpus import Corpus,identity,canonical,language,bucket,informative

BASE='https://data.commoncrawl.org/'

def shard(job):
    path,size,parser=job;stats=Counter();rows=[]
    for attempt in range(3):
        try:
            response=requests.get(BASE+path,headers={'Range':f'bytes=0-{size-1}','User-Agent':'passbert-research/0.1 (CommonCrawl archive only)'},stream=True,timeout=(15,90))
            break
        except requests.RequestException:
            if attempt==2:return path,[],{'request_error':1}
            time.sleep(2**attempt)
    if response.status_code!=206:response.close();return path,[],{'http_status:'+str(response.status_code):1}
    raw=bytearray()
    try:
        for chunk in response.iter_content(1024*1024):
            raw.extend(chunk)
            if len(raw)>size:raise ValueError('Range response exceeded byte budget')
    finally:response.close()
    stats['download_bytes']=len(raw)
    iterator=ArchiveIterator(io.BytesIO(raw))
    try:
        for record in iterator:
            stats['warc_records']+=1
            if record.rec_type!='response' or not record.http_headers:continue
            if record.http_headers.get_statuscode()!='200':continue
            if 'html' not in record.http_headers.get_header('Content-Type','').lower():continue
            try:
                url=record.rec_headers.get_header('WARC-Target-URI','')
                if not url.startswith(('https://','http://')):continue
                site,host,split=identity(url)
                body=record.content_stream().read(1_000_001)
                if len(body)>1_000_000:stats['oversize']+=1;continue
                lower=body.lower()
                if b'<input' not in lower and b'<textarea' not in lower and b'<select' not in lower:continue
                stats['candidate_pages']+=1
                content_type=record.http_headers.get_header('Content-Type','')
                import re
                match=re.search(r'charset\s*=\s*["\x27]?([\w-]+)',content_type,re.I)
                encoding=match[1] if match else 'utf-8'
                try:html=body.decode(encoding,errors='replace')
                except LookupError:html=body.decode('utf-8',errors='replace')
                # HTML5 normalization first; policy/extraction is shared with the regular parser.
                if parser=='native':forms,annotation_views=extract_fast(html)
                else:
                    normalized=LexborHTMLParser(html).html;annotation_views=[]
                    forms=extract(normalized,_parser='lxml',_annotation_views=annotation_views)
                for index,form in enumerate(forms):
                    if not informative(form):stats['uninformative']+=1;continue
                    lang,basis=language(html,form)
                    if lang not in ['en','ja']:stats['other_language']+=1;continue
                    rows.append({'schema_version':2,'record_id':canonical(form),'site_id':site,'host_id':host,'split':split,'language':lang,'language_basis':basis,'bucket':bucket(form),'source':'commoncrawl','source_ref':{'crawl':path.split('/')[1],'warc':path,'offset':iterator.get_record_offset(),'form_index':index},'signature':signature(form),'template_family':canonical(form),'form':form,'annotation_view':annotation_views[index],'annotation_policy':'semantic-annotation-v2','label_status':'unlabeled','license':'source-dependent-unknown','redistribution_allowed':False,'extraction':'privacy-v1;lexbor-native-v1' if parser=='native' else 'privacy-v1;lexbor-html5+lxml','collected_at':datetime.now(timezone.utc).isoformat()})
                stats['extracted_forms']+=len(forms)
            except Exception as error:stats['parse_error:'+type(error).__name__]+=1
    except Exception as error:stats['tail_or_stream_error:'+type(error).__name__]+=1
    return path,rows,dict(stats)

def safe_shard(job):
    try:return shard(job)
    except Exception as error:return job[0],[],{'worker_error:'+type(error).__name__:1}

def main():
    p=argparse.ArgumentParser();p.add_argument('--target',type=int,default=10000);p.add_argument('--crawl',default='CC-MAIN-2026-43');p.add_argument('--output',default='artifacts/corpus-10k');p.add_argument('--workers',type=int,default=4);p.add_argument('--shard-mib',type=int,default=64);p.add_argument('--max-shards',type=int,default=256);p.add_argument('--site-cap',type=int,default=12);p.add_argument('--parser',choices=['native','reference'],default='native');args=p.parse_args()
    if min(args.target,args.workers,args.shard_mib,args.max_shards,args.site_cap)<=0:p.error('Counts, workers, and byte budgets must be positive')
    root=Path(args.output);root.mkdir(parents=True,exist_ok=True);db=Corpus(root/'corpus.sqlite');started=time.monotonic()
    response=requests.get(BASE+f'crawl-data/{args.crawl}/warc.paths.gz',timeout=60);response.raise_for_status()
    paths=gzip.decompress(response.content).decode().splitlines();random.Random(20261109).shuffle(paths)
    done={p for p, in db.db.execute('SELECT path FROM shards')}
    if any(path.split('/')[1]!=args.crawl for path in done):raise SystemExit('Use a separate output directory for a different crawl')
    todo=[path for path in paths if path not in done][:args.max_shards]
    totals=Counter();reasons=Counter();current=db.count();submitted=0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        while current<args.target and submitted<len(todo) and not (root/'STOP').exists():
            jobs=[(path,args.shard_mib*1024*1024,args.parser) for path in todo[submitted:submitted+args.workers]];submitted+=len(jobs)
            for path,rows,stats in pool.map(safe_shard,jobs):
                totals.update(stats)
                for row in rows:
                    if current>=args.target:break
                    result=db.insert(row,args.site_cap);reasons[result]+=1
                    if result=='accepted':current+=1
                db.db.execute('INSERT OR REPLACE INTO shards VALUES (?,?)',(path,json.dumps(stats)));db.db.commit()
                print(json.dumps({'accepted_total':current,'processed_shards':len(done)+submitted,'candidate_pages':totals['candidate_pages'],'download_mib':round(totals['download_bytes']/1024**2),'elapsed_seconds':round(time.monotonic()-started),'rejections':dict(reasons)}),flush=True)
            if submitted%16==0 or current>=args.target:
                report=db.export(root);report.update({'target':args.target,'crawl':args.crawl,'complete':current>=args.target,'processing_stats_this_run':dict(totals),'selection':'seeded random WARC files; first bounded byte range per file; max forms per registrable site','byte_budget_per_shard':args.shard_mib*1024*1024})
                (root/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    report=db.export(root);report.update({'target':args.target,'crawl':args.crawl,'complete':current>=args.target,'processing_stats_this_run':dict(totals),'selection':'seeded random WARC files; prefix range; site cap; nonrepresentative pilot corpus','license':'source-dependent; do not assume Common Crawl grants rights to source content'})
    (root/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False),flush=True)
    if current<args.target:raise SystemExit(2)

if __name__=='__main__':main()
