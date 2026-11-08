"""Offline-only, allowlisted extraction. Never retain raw HTML or input values."""
import hashlib
import json
import random
import re
from pathlib import Path
from bs4 import BeautifulSoup, Comment

FIELDS = ['username', 'email', 'current-password', 'new-password', 'one-time-code', 'search', 'other']
FORMS = ['login', 'signup', 'password-recovery', 'otp', 'search', 'other']
# Deliberately a closed semantic vocabulary: arbitrary DOM text can contain secrets.
WORDS = ['username','user','email','password','current','new','confirm','code','otp','search','login','sign','in','up','register','reset','recover','next','continue','verification','contact','message','ログイン','ユーザー','メール','パスワード','新規','登録','確認','認証','コード','検索','再設定','次へ','問い合わせ']
PATTERN = re.compile('|'.join(map(re.escape, sorted(WORDS, key=len, reverse=True))), re.I)

def safe(text):
    return ' '.join(m.group().lower() for m in PATTERN.finditer(str(text)[:2048]))[:192]

def extract(html):
    soup = BeautifulSoup(html[:1_000_000], 'html5lib')
    blocked = {'script','style','template','noscript','input','textarea','select','option'}
    for node in soup(['script','style','template','noscript']):
        node.decompose()
    def text(node):
        if node is None: return ''
        return ' '.join(str(t) for t in node.find_all(string=True)
                        if not isinstance(t,Comment) and not any(p.name in blocked or p.get('contenteditable','false').lower() != 'false' for p in t.parents))
    def eligible(el):
        if el.get('type','text').lower() in ['hidden','submit','button','checkbox','radio','file','image','reset']: return False
        for node in [el,*el.parents]:
            if node.has_attr('hidden') or node.get('aria-hidden','').lower() == 'true': return False
            style = re.sub(r'\s+', '', node.get('style','').lower())
            if re.search(r'(?:^|;)(?:display:none|visibility:hidden)(?:;|$|!)',style): return False
        return True
    controls = [el for el in soup.find_all(['input','textarea','select']) if eligible(el)]
    groups = [(f,[]) for f in soup.find_all('form')]
    def group_for(el):
        if el.has_attr('form'):
            owner=soup.find('form',id=el['form'])
        else: owner=el.find_parent('form')
        if owner is not None: return owner
        for parent in el.parents:
            if parent.name in ['body','html','[document]']: break
            if not parent.find('form') and parent.find(['button','input'], attrs={'type':'submit'}): return parent
            if not parent.find('form') and parent.find('button'): return parent
        return soup.body
    for el in controls:
        owner=group_for(el)
        if owner is None: continue
        entry=next((pair for pair in groups if pair[0] is owner),None)
        if entry is None: entry=(owner,[]);groups.append(entry)
        if len(entry[1])<64: entry[1].append(el)
    output=[]
    for group,elements in groups:
        if not elements: continue
        fields=[]
        for el in elements:
            label=soup.find('label',attrs={'for':el.get('id')}) if el.get('id') else None
            if label is None: label=el.find_parent('label')
            references=[soup.find(id=x) for x in el.get('aria-labelledby','').split()[:8]]
            kind=el.get('type','text').lower()
            if kind not in ['text','email','password','tel','number','search','url']: kind='text'
            fields.append({'type':kind,'hint':safe(' '.join([el.get('name',''),el.get('id',''),el.get('placeholder',''),el.get('aria-label',''),text(label),*(text(n) for n in references)])),
                           'autocomplete':' '.join(t for t in el.get('autocomplete','').lower().split() if t in FIELDS)})
        headings=group.find_all(['h1','h2','h3'])
        if not headings:
            cursor=group
            for _ in range(3):
                for sib in cursor.previous_siblings:
                    if not getattr(sib,'name',None): continue
                    if sib.name=='form' or sib.find('form'): break
                    candidates=([sib] if sib.name in ['h1','h2','h3'] else sib.find_all(['h1','h2','h3']))
                    if candidates: headings=[candidates[-1]];break
                if headings or cursor.parent is None or cursor.parent.name in ['body','html','[document]']: break
                cursor=cursor.parent
        output.append({'context':safe(' '.join(text(n) for n in headings+group.find_all('button'))),'fields':fields})
        if len(output)>=32: break
    return output

def serialize(form):
    return '[CLS] ' + form['context'] + ' ' + ' '.join('[FLD] ' + ' '.join(f[k] for k in ['type','hint','autocomplete']) for f in form['fields'])

def signature(form):
    return hashlib.sha256(serialize(form).encode()).hexdigest()

def generate(root, sites=240, seed=42):
    """Each site owns a distinct template family; duplicates are removed globally."""
    rng = random.Random(seed)
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    rows = {s: [] for s in ['train','val','test']}; seen = set()
    purposes = {
        'login': [('username','email'), ('current-password',)],
        'signup': [('email',), ('new-password',), ('new-password',)],
        'password-recovery': [('email',)], 'otp': [('one-time-code',)],
        'search': [('search',)], 'other': [('other',)]}
    captions = {'login': ['Sign in','ログイン'], 'signup':['Sign up register','新規 登録'], 'password-recovery':['Reset recover','パスワード 再設定'], 'otp':['Verification code','認証 コード'], 'search':['Search','検索'], 'other':['Contact message','問い合わせ']}
    hints = {'username':['username user','ユーザー'], 'email':['email','メール'], 'current-password':['current password','パスワード'], 'new-password':['new password confirm','新規 パスワード 確認'], 'one-time-code':['otp code','認証 コード'], 'search':['search','検索'], 'other':['message','問い合わせ']}
    site_ids = list(range(sites)); rng.shuffle(site_ids)
    for rank, site in enumerate(site_ids):
        split = 'train' if rank < sites*.8 else 'val' if rank < sites*.9 else 'test'
        # independently assigned site templates, without site identifiers in model text
        layout = site % 4
        for lang in range(2):
            for purpose, spec in purposes.items():
                labels = [rng.choice(options) for options in spec]
                caption = captions[purpose][lang]
                inputs = []
                for i, label in enumerate(labels):
                    hint = hints[label][lang]
                    kind = 'password' if 'password' in label else ('email' if label == 'email' else 'text')
                    ac = label if rng.random() < .45 else 'off'
                    if layout == 1: kind = 'text'
                    if layout == 2: ac = 'off'
                    # Random semantic distractors provide varied surface forms; no external data.
                    extra = ' '.join(rng.sample(WORDS, rng.randint(0,3)))
                    inputs.append(f'<label for="f{i}">{hint if layout != 3 else ""}</label><input id="f{i}" type="{kind}" placeholder="{hint} {extra}" autocomplete="{ac}">')
                html = f'<form><h2>{caption}</h2>{"".join(inputs)}<button>{caption}</button></form>'
                form = extract(html)[0]; sig = signature(form)
                if sig in seen: continue
                seen.add(sig)
                rows[split].append({'schema_version':1,'site_id':f'synthetic-{site}.example','template_family':f'site-{site}','language':['en','ja'][lang],'source':'synthetic-v1','license':'BSD-3-Clause','signature':sig,'form':form,'form_label':purpose,'field_labels':labels})
    for split, data in rows.items():
        (root / f'{split}.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in data))
    (root/'manifest.json').write_text(json.dumps({'seed':seed,'sites':sites,'counts':{s:len(r) for s,r in rows.items()},'license':'BSD-3-Clause','generator':'synthetic-v1'},indent=2))
    return rows

def load(path):
    rows=[json.loads(line) for line in Path(path).read_text().splitlines() if line]
    if any(row.get('evaluation_only') for row in rows):
        raise ValueError('Evaluation-only data must never enter training/tokenizer datasets')
    return rows
