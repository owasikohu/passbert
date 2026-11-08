"""Unlabeled corpus bookkeeping. Only privacy-filtered features enter SQLite/JSONL."""
import hashlib
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit
import tldextract
from passbert.data import signature

PSL=tldextract.TLDExtract(suffix_list_urls=(),include_psl_private_domains=True,cache_dir=None)
IMPORTANT={'username','user','email','password','current','new','confirm','code','otp','search','login','sign','register','reset','recover','verification','contact','message','ログイン','ユーザー','メール','パスワード','新規','登録','確認','認証','コード','検索','再設定','問い合わせ'}

def digest(value):return hashlib.sha256(value.encode()).hexdigest()

def identity(url):
    host=(urlsplit(url).hostname or '').lower().rstrip('.')
    if not host:raise ValueError('Missing hostname')
    parsed=PSL(host);site=parsed.top_domain_under_public_suffix or host
    site_id='site-sha256:'+digest(site)
    value=int(digest(site)[:8],16)%100
    return site_id,'host-sha256:'+digest(host),'train' if value<80 else 'val' if value<90 else 'test'

def canonical(form):
    def tokens(value):return ' '.join(sorted(set(value.split())))
    obj={'context':tokens(form['context']),'fields':[{'type':f['type'],'hint':tokens(f['hint']),'autocomplete':tokens(f['autocomplete'])} for f in form['fields']]}
    return digest(json.dumps(obj,ensure_ascii=False,sort_keys=True))

def language(html,form):
    match=re.search(r'<html\b[^>]*\blang\s*=\s*["\x27]?([a-zA-Z-]+)',html[:16384],re.I)
    if match:
        lang=match[1].lower().split('-')[0]
        if lang in ['en','ja']:return lang,'html-lang'
        return 'other','html-lang'
    text=form['context']+' '+' '.join(f['hint'] for f in form['fields'])
    if re.search('[\u3040-\u30ff\u4e00-\u9fff]',text):return 'ja','semantic-hint'
    if any(t in IMPORTANT for t in text.split()):return 'en','semantic-hint-inferred'
    return 'unknown','none'

def bucket(form):
    text=form['context']+' '+' '.join(f['hint']+' '+f['autocomplete'] for f in form['fields'])
    if any(f['type']=='password' for f in form['fields']) or any(t in text for t in ['password','ログイン','パスワード','one-time-code','otp']):return 'auth-candidate'
    if len(form['fields'])==1 and form['fields'][0]['type']=='search':return 'search-negative'
    return 'general'

def informative(form):
    if any(f['type'] in ['password','email','search'] or f['autocomplete'] for f in form['fields']):return True
    text=form['context']+' '+' '.join(f['hint'] for f in form['fields'])
    return bool(set(text.split())&IMPORTANT)

class Corpus:
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS forms (fingerprint TEXT PRIMARY KEY, site TEXT NOT NULL, split TEXT NOT NULL, language TEXT NOT NULL, bucket TEXT NOT NULL, row_json TEXT NOT NULL)')
        self.db.execute('CREATE INDEX IF NOT EXISTS site_index ON forms(site)')
        self.db.execute('CREATE TABLE IF NOT EXISTS shards (path TEXT PRIMARY KEY, stats TEXT NOT NULL)');self.db.commit()
    def count(self):return self.db.execute('SELECT count(*) FROM forms').fetchone()[0]
    def insert(self,row,max_per_site=12):
        if self.db.execute('SELECT count(*) FROM forms WHERE site=?',(row['site_id'],)).fetchone()[0]>=max_per_site:return 'site_cap'
        try:
            self.db.execute('INSERT INTO forms VALUES (?,?,?,?,?,?)',(row['template_family'],row['site_id'],row['split'],row['language'],row['bucket'],json.dumps(row,ensure_ascii=False)))
            return 'accepted'
        except sqlite3.IntegrityError:return 'duplicate'
    def export(self,root):
        root=Path(root);root.mkdir(parents=True,exist_ok=True)
        counts=Counter();sites=set();splits={k:set() for k in ['train','val','test']}
        with (root/'unlabeled.jsonl.tmp').open('w') as allrows:
            handles={split:(root/f'{split}.jsonl.tmp').open('w') for split in splits}
            try:
                for value, in self.db.execute('SELECT row_json FROM forms ORDER BY fingerprint'):
                    row=json.loads(value);row['evaluation_only']=row['split']!='train';value=json.dumps(row,ensure_ascii=False);line=value+'\n';allrows.write(line);handles[row['split']].write(line)
                    counts['annotation_policy:'+row.get('annotation_policy','privacy-v1')]+=1
                    counts['total']+=1;counts['language:'+row['language']]+=1;counts['language_basis:'+row['language_basis']]+=1;counts['bucket:'+row['bucket']]+=1;counts['split:'+row['split']]+=1
                    sites.add(row['site_id']);splits[row['split']].add(row['site_id'])
            finally:
                for h in handles.values():h.close()
        for name in ['unlabeled','train','val','test']:(root/f'{name}.jsonl.tmp').replace(root/f'{name}.jsonl')
        assert all(not splits[a]&splits[b] for a,b in [('train','val'),('train','test'),('val','test')])
        return {'counts':dict(counts),'sites':len(sites),'site_overlap':0,'dedup':'globally unique canonical token-set features; not fuzzy/semantic dedup','labels':'none','license':'source-dependent; no redistribution license assigned','psl':'tldextract bundled PSL; private suffixes enabled; no live PSL updates'}
