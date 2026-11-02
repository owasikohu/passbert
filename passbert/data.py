"""Offline-only, allowlisted extraction. Never retain raw HTML or input values."""
import hashlib
import json
import random
import re
from pathlib import Path
from bs4 import BeautifulSoup

FIELDS = ['username', 'email', 'current-password', 'new-password', 'one-time-code', 'search', 'other']
FORMS = ['login', 'signup', 'password-recovery', 'otp', 'search', 'other']
# Deliberately a closed semantic vocabulary: arbitrary DOM text can contain secrets.
WORDS = ['username','user','email','password','current','new','confirm','code','otp','search','login','sign','in','up','register','reset','recover','next','continue','verification','contact','message','ログイン','ユーザー','メール','パスワード','新規','登録','確認','認証','コード','検索','再設定','次へ','問い合わせ']
PATTERN = re.compile('|'.join(map(re.escape, sorted(WORDS, key=len, reverse=True))), re.I)

def safe(text):
    return ' '.join(m.group().lower() for m in PATTERN.finditer(str(text)[:2048]))[:192]

def extract(html):
    soup = BeautifulSoup(html[:1_000_000], 'html5lib')
    for node in soup(['script','style','template','noscript']):
        node.decompose()
    output = []
    groups = list(soup.find_all('form'))
    # Explicit fallback for form-less pages. Complex SPA grouping remains a coverage limitation.
    if not groups:
        groups = [soup.body]
    for group in groups[:32]:
        fields = []
        for el in group.find_all(['input','textarea','select'])[:64]:
            if el.get('type','text').lower() in ['hidden','submit','button','checkbox','radio','file','image','reset'] or el.has_attr('hidden') or el.get('aria-hidden') == 'true':
                continue
            label = soup.find('label', attrs={'for': el.get('id')}) if el.get('id') else None
            if label is None:
                label = el.find_parent('label')
            # Never use label.text: nested textarea content may be user data.
            label_text = ' '.join(str(t) for t in label.find_all(string=True) if t.parent.name not in ['textarea','select','option','input']) if label else ''
            kind = el.get('type','text').lower()
            if kind not in ['text','email','password','tel','number','search','url']:
                kind = 'text'
            fields.append({'type': kind, 'hint': safe(' '.join([el.get('name',''), el.get('id',''), el.get('placeholder',''), el.get('aria-label',''), label_text])), 'autocomplete': ' '.join(t for t in el.get('autocomplete','').split() if t in FIELDS)})
        if fields:
            headings = group.find_all(['h1','h2','h3'])
            buttons = group.find_all('button')
            context_text = ' '.join(str(t) for n in headings + buttons for t in n.find_all(string=True) if not any(p.name in ['input','textarea','select','option'] for p in t.parents))
            output.append({'context': safe(context_text), 'fields': fields})
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
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]
