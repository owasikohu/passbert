"""General-purpose varied supervised synthesis. No evaluation fixtures or live pages are read."""
import hashlib
import html
import json
import random
from pathlib import Path
from passbert.data import extract,signature

CAPTIONS={
 'login':[['Sign in','Login','Sign in to continue','Continue sign in'],['ログイン','ログイン 確認','ユーザー ログイン']],
 'signup':[['Sign up','Register','Create new user','Register new user'],['新規 登録','ユーザー 登録','新規 ユーザー']],
 'password-recovery':[['Reset password','Recover password','Password reset'],['パスワード 再設定','パスワード 再設定 確認']],
 'otp':[['Verification code','OTP','Confirm code'],['認証 コード','コード 確認','認証 確認']],
 'search':[['Search','Search query'],['検索','検索 確認']],
 'other':[['Contact','Message','Contact message'],['問い合わせ','問い合わせ 確認']]}
HINTS={
 'username':[['Username','User','User login','Username or email'],['ユーザー','ユーザー 確認']],
 'email':[['Email','Email address','User email'],['メール','メール 確認']],
 'current-password':[['Password','Current password'],['パスワード','パスワード 確認']],
 'new-password':[['New password','Confirm new password','Password'],['新規 パスワード','パスワード 確認','パスワード']],
 'one-time-code':[['Code','OTP','Verification code'],['コード','認証 コード']],
 'search':[['Search','Search query'],['検索']], 'other':[['Message','Contact'],['問い合わせ']]}

def generate_v2(root,sites=360,seed=20261108):
 rng=random.Random(seed);rows={k:[] for k in ['train','val','test']};seen=set();order=list(range(sites));rng.shuffle(order)
 for rank,site in enumerate(order):
  split='train' if rank<sites*.8 else 'val' if rank<sites*.9 else 'test'
  for lang in range(2):
   for purpose in CAPTIONS:
    for variant in range(3):
     identifier=rng.choice(['username','email'])
     specs={'login':[identifier]+(['current-password'] if rng.random()<.8 else []),'signup':['email','new-password']+(['new-password'] if rng.random()<.6 else []),'password-recovery':['email'],'otp':['one-time-code']*rng.choice([1,1,1,4,6]),'search':['search'],'other':['other']}
     labels=specs[purpose];caption=rng.choice(CAPTIONS[purpose][lang]);parts=[]
     for i,label in enumerate(labels):
      hint=rng.choice(HINTS[label][lang]);kind='password' if 'password' in label else ('email' if label=='email' else ('search' if label=='search' else 'text'))
      if kind=='password' and rng.random()<.12:kind='text'
      ac=label if rng.random()<.4 else rng.choice(['off','on',''])
      mode=rng.randrange(6);identifier_attr=f'field{site}_{i}'
      name=rng.choice([hint,'',f'f{site}_{i}'])
      attrs=f'id="{identifier_attr}" name="{html.escape(name)}" type="{kind}" autocomplete="{ac}"'
      if mode==0:part=f'<label for="{identifier_attr}">{hint}</label><input {attrs}>'
      elif mode==1:part=f'<label>{hint}<input {attrs}></label>'
      elif mode==2:part=f'<input {attrs} placeholder="{hint}">'
      elif mode==3:part=f'<input {attrs} aria-label="{hint}">'
      elif mode==4:part=f'<span id="label{i}">{hint}</span><input {attrs} aria-labelledby="label{i}">'
      else:part=f'<input {attrs}>' if ac==label or kind in ['password','email','search'] else f'<input {attrs} placeholder="{hint}">'
      parts.append(part)
     button=rng.choice([caption,'Continue','Next','確認','次へ'])
     style=rng.randrange(3);inside=f'{"".join(parts)}<button>{button}</button>'
     markup=f'<section><h2>{caption}</h2><form>{inside}</form></section>' if style==0 else (f'<div><h2>{caption}</h2>{inside}</div>' if style==1 else f'<form><h2>{caption}</h2>{inside}</form>')
     forms=extract(markup)
     if len(forms)!=1 or len(forms[0]['fields'])!=len(labels):raise ValueError('Synthesis/extraction label mismatch')
     form=forms[0];sig=signature(form)
     if sig in seen:continue
     seen.add(sig)
     rows[split].append({'schema_version':1,'site_id':f'v2-{site}.example','template_family':f'v2-site-{site}','language':['en','ja'][lang],'source':'synthetic-v2','license':'BSD-3-Clause','signature':sig,'form':form,'form_label':purpose,'field_labels':labels})
 root=Path(root);root.mkdir(parents=True,exist_ok=True)
 for split,data in rows.items():(root/f'{split}.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in data))
 (root/'manifest.json').write_text(json.dumps({'seed':seed,'sites':sites,'generator':'synthetic-v2','counts':{k:len(v) for k,v in rows.items()},'evaluation_inputs_used':False,'license':'BSD-3-Clause'},indent=2))
 return rows
