"""Validate corpus privacy schema, canonical dedup, and reserved site partitions."""
import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from passbert.corpus import canonical
from passbert.data import signature,WORDS,FIELDS
from passbert.annotation import TERMS,AUTOCOMPLETE

p=argparse.ArgumentParser();p.add_argument('--root',default='artifacts/corpus-10k');args=p.parse_args();root=Path(args.root)
counts=Counter();sites={key:set() for key in ['train','val','test']};fingerprints=set();signatures=set();errors=[]
def check_features(form,terms,allowed_ac,max_length):
    if set(form)!={'context','fields'}:return False
    for value in [form['context'],*(f['hint'] for f in form['fields'])]:
        # Python's case-insensitive regex also recognizes dotless/dotted I and long s.
        tokens=[token.replace('ı','i').replace('i\u0307','i').replace('ſ','s').replace('K','k') for token in value.split()]
        for index,token in enumerate(tokens):
            if token not in terms and not (index==len(tokens)-1 and len(value)==max_length and any(t.startswith(token) for t in terms)):return False
    for field in form['fields']:
        if set(field)!={'type','hint','autocomplete'}:return False
        if field['type'] not in ['text','email','password','tel','number','search','url']:return False
        if any(t not in allowed_ac for t in field['autocomplete'].split()):return False
    return True
for line in (root/'unlabeled.jsonl').open():
 row=json.loads(line);counts['rows']+=1
 if not check_features(row['form'],WORDS,FIELDS,192):errors.append('unsafe baseline schema')
 if row['template_family']!=canonical(row['form']) or row['signature']!=signature(row['form']):errors.append('fingerprint mismatch')
 if row['template_family'] in fingerprints:errors.append('canonical duplicate')
 fingerprints.add(row['template_family']);signatures.add(row['signature']);sites[row['split']].add(row['site_id'])
 value=int(row['site_id'].split(':')[1][:8],16)%100;expected='train' if value<80 else 'val' if value<90 else 'test'
 if row['split']!=expected:errors.append('site split mismatch')
 if row.get('evaluation_only')!=(row['split']!='train'):errors.append('evaluation reservation mismatch')
 if 'annotation_view' in row:
    counts['annotation_views']+=1
    if not check_features(row['annotation_view'],TERMS,AUTOCOMPLETE,256):errors.append('unsafe annotation schema')
    if len(row['annotation_view']['fields'])!=len(row['form']['fields']):errors.append('annotation alignment mismatch')
 if row['label_status']!='unlabeled' or any(k in row for k in ['form_label','field_labels']):errors.append('unexpected labels')
 counts['language:'+row['language']]+=1;counts['language_basis:'+row['language_basis']]+=1;counts['bucket:'+row['bucket']]+=1
 counts['fields']+=len(row['form']['fields']);counts['split:'+row['split']]+=1
for a,b in [('train','val'),('train','test'),('val','test')]:
 if sites[a]&sites[b]:errors.append('cross-split sites')
source_stats=Counter()
with sqlite3.connect(root/'corpus.sqlite') as db:
 for value, in db.execute('SELECT stats FROM shards'):source_stats.update(json.loads(value))
result={'counts':dict(counts),'sites':len(set.union(*sites.values())),'errors':dict(Counter(errors)),'source_stats_completed_shards':dict(source_stats),'files_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('*.jsonl')},'limits':['No fuzzy/semantic near-duplicate guarantee','Language inferred from semantic hints is not verified','Source rights are not inherited from Common Crawl','Reserved test sites may still have appeared in Zap training']}
(root/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
if errors:raise SystemExit(1)
