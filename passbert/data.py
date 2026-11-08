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

def extract(html, *, _parser="html5lib", _annotation_views=None):
    if _annotation_views is not None:
        from passbert.annotation import sanitize as annotation_safe, AUTOCOMPLETE as annotation_ac
    soup = BeautifulSoup(html[:1_000_000], _parser)
    blocked = {'script','style','template','noscript','input','textarea','select','option'}
    for node in soup(['script','style','template','noscript']):
        node.decompose()
    by_id={}
    labels_by_for={}
    forms_by_id={}
    for node in soup.find_all(attrs={'id':True}):by_id.setdefault(node['id'],node)
    for node in soup.find_all('label',attrs={'for':True}):labels_by_for.setdefault(node['for'],node)
    for node in soup.find_all('form',attrs={'id':True}):forms_by_id.setdefault(node['id'],node)
    visibility={}
    def visible(node):
        if node is None:return True
        key=id(node)
        if key in visibility:return visibility[key]
        style=re.sub(r'\s+','',node.get('style','').lower())
        result=not (node.has_attr('hidden') or node.get('aria-hidden','').lower()=='true' or re.search(r'(?:^|;)(?:display:none|visibility:hidden)(?:;|$|!)',style))
        result=result and visible(node.parent);visibility[key]=result;return result
    def text(node):
        if node is None: return ''
        return ' '.join(str(t) for t in node.find_all(string=True)
                        if not isinstance(t,Comment) and not any(p.name in blocked or p.get('contenteditable','false').lower() != 'false' for p in t.parents))
    def eligible(el):
        if el.get('type','text').lower() in ['hidden','submit','button','checkbox','radio','file','image','reset']: return False
        return visible(el)
    controls = [el for el in soup.find_all(['input','textarea','select']) if eligible(el)]
    groups = [(f,[]) for f in soup.find_all('form')]
    group_tests={}
    def group_for(el):
        if el.has_attr('form'):
            owner=forms_by_id.get(el['form'])
        else: owner=el.find_parent('form')
        if owner is not None: return owner
        for parent in el.parents:
            if parent.name in ['body','html','[document]']: break
            key=id(parent)
            if key not in group_tests:
                group_tests[key]=not parent.find('form') and bool(parent.find(['button','input'],attrs={'type':'submit'}) or parent.find('button'))
            if group_tests[key]:return parent
        return soup.body
    group_index={id(pair[0]):pair for pair in groups}
    for el in controls:
        owner=group_for(el)
        if owner is None: continue
        entry=group_index.get(id(owner))
        if entry is None: entry=(owner,[]);groups.append(entry);group_index[id(owner)]=entry
        if len(entry[1])<64: entry[1].append(el)
    output=[]
    for group,elements in groups:
        if not elements: continue
        fields=[];annotation_fields=[]
        for el in elements:
            label=labels_by_for.get(el.get('id')) if el.get('id') else None
            if label is None: label=el.find_parent('label')
            references=[by_id.get(x) for x in el.get('aria-labelledby','').split()[:8]]
            kind=el.get('type','text').lower()
            if kind not in ['text','email','password','tel','number','search','url']: kind='text'
            raw_hint=' '.join([el.get('name',''),el.get('id',''),el.get('placeholder',''),el.get('aria-label',''),text(label),*(text(n) for n in references)])
            ac=el.get('autocomplete','').lower().split()
            fields.append({'type':kind,'hint':safe(raw_hint),'autocomplete':' '.join(t for t in ac if t in FIELDS)})
            if _annotation_views is not None:
                annotation_fields.append({'type':kind,'hint':annotation_safe(raw_hint),'autocomplete':' '.join(t for t in ac if t in annotation_ac)})
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
        context=' '.join(text(n) for n in headings+group.find_all('button'))
        output.append({'context':safe(context),'fields':fields})
        if _annotation_views is not None:_annotation_views.append({'context':annotation_safe(context),'fields':annotation_fields})
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
    if any(row.get('label_status') in ['unlabeled','proposal'] for row in rows):
        raise ValueError('Unlabeled forms and proposals require explicit audited label promotion')
    return rows
