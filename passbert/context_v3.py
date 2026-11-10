"""Boundary-aware, closed-vocabulary evidence. Raw text/values never enter the view."""
import re
import unicodedata
from passbert.annotation import TERMS,AUTOCOMPLETE

VERSION='semantic-context-v3'
ALIASES={term:term for term in TERMS}
ALIASES.update({
 'userid':'user id','firstname':'first name','lastname':'last name','givenname':'given name','familyname':'family name','fullname':'full name','displayname':'display name','emailaddress':'email address','e-mail':'email','newpassword':'new password','currentpassword':'current password','oldpassword':'old password','confirmpassword':'confirm password','repeatpassword':'repeat password','loginname':'login name','loginform':'login form','signupform':'signup form','pwd':'password',
 'ユーザー名':'username','ユーザ名':'username','ユーザーネーム':'username','ログインid':'login id','会員id':'member id','表示名':'display name','氏名':'full name','お名前':'name','名前':'name','フルネーム':'full name','姓':'family name','名':'name','会社名':'company name',
 'メールアドレス':'email','メール':'email','電話番号':'phone number','携帯電話':'mobile phone','郵便番号':'postal code','都道府県':'state region','市区町村':'city','住所':'address',
 '新しいパスワード':'new password','現在のパスワード':'current password','旧パスワード':'old password','新パスワード':'new password','パスワード再設定':'password reset','パスワード変更':'password change','パスワードを忘れた':'forgot password','パスワードをお忘れ':'forgot password','パスワード確認':'confirm password','変更前':'current','変更後':'new','新しい':'new','現在':'current','再入力':'repeat','確認用':'confirm','パスワード':'password',
 '会員登録':'member register','新規登録':'new register','アカウント作成':'account register','ログイン':'login','ログオン':'login','サインイン':'sign in','サインアップ':'sign up','メールマガジン':'newsletter','メルマガ':'newsletter','配信停止':'unsubscribe','登録解除':'unsubscribe','購読':'subscribe',
 '認証コード':'verification code','確認コード':'verification code','ワンタイムパスワード':'one time password','画像認証':'image captcha','お問い合わせ':'contact','問い合わせ':'contact','お問合せ':'contact','件名':'subject','メッセージ':'message','内容':'message','検索':'search',
})
EXTRA=['label','placeholder','identifier','description','heading','group','legend','form','id','display','full','old','existing','sent','sms','one','time','image','challenge','characters','required','optional','enter','show','hide','forgotten','unsubscribe','question','business','department','filter','keyword','query','confirm','reset','change']
ALIASES.update({term:term for term in EXTRA})
# Split known identifier boundaries first, then match complete Latin words, not substrings.
PATTERN=re.compile('|'.join('(?<![a-z0-9])'+re.escape(key)+'(?![a-z0-9])' if re.search('[a-z]',key) else re.escape(key) for key in sorted(ALIASES,key=lambda x:(-len(x),x))))
ALLOWED=set(word for value in ALIASES.values() for word in value.split())

def sanitize(text,limit=512):
 text=unicodedata.normalize('NFKC',str(text)[:4096])
 text=re.sub(r'([a-z0-9])([A-Z])',r'\1 \2',text)
 text=re.sub(r'([A-Z])([A-Z][a-z])',r'\1 \2',text).casefold().replace('ı','i').replace('i\u0307','i')
 text=re.sub(r'[_\d]+',' ',text)
 words=[]
 for match in PATTERN.finditer(text):words.extend(ALIASES[match[0]].split())
 filtered=[]
 for word in words:
  if word=='in' and (not filtered or filtered[-1] not in ['sign','log']):continue
  if word=='up' and (not filtered or filtered[-1]!='sign'):continue
  if not filtered or filtered[-1]!=word:filtered.append(word)
 result=' '.join(filtered)
 if len(result)>limit:result=result[:limit].rsplit(' ',1)[0]
 return result


def render(root,elements,headings,helpers):
 text=helpers['text'];visible=helpers['visible'];by_id=helpers['by_id']
 def hint(el):
  a=el.attributes or {};label=None
  label=helpers['labels'].get(a.get('id')) if a.get('id') else None
  if label is None:
   parent=el.parent
   while parent is not None and parent.tag!='label':parent=parent.parent
   label=parent
  refs=[by_id.get(value) for value in (a.get('aria-labelledby') or '').split()[:8]]
  label_text=' '.join([text(label),a.get('aria-label') or '',*(text(n) for n in refs)])
  descriptions=[by_id.get(value) for value in (a.get('aria-describedby') or '').split()[:8]]
  description=' '.join([*(text(n) for n in descriptions),a.get('title') or ''])
  parent=el.parent
  for _ in range(2):
   if parent is None or parent.tag in ['body','html','form']:break
   if len(parent.css('input,textarea,select'))==1:
    description+=' '+text(parent)
    description+=' '+' '.join((n.attributes or {}).get('alt') or '' for n in parent.css('img') if visible(n))
    break
   parent=parent.parent
  legend='';parent=el.parent
  while parent is not None and parent.mem_id!=root.mem_id:
   if parent.tag=='fieldset':legend=' '.join(text(n) for n in parent.css('legend'));break
   parent=parent.parent
  channels=[('label',label_text),('placeholder',a.get('placeholder') or ''),('identifier',' '.join([a.get('name') or '',a.get('id') or ''])),('description',description),('group',legend)]
  parts=[]
  for key,value in channels:
   cleaned=sanitize(value,128)
   if cleaned:parts.extend([key,cleaned])
  combined=' '.join(parts)
  if len(combined)>512:combined=combined[:512].rsplit(' ',1)[0]
  kind=(a.get('type') or 'text').lower()
  if kind not in ['text','email','password','tel','number','search','url']:kind='text'
  return {'type':kind,'hint':combined,'autocomplete':' '.join(t for t in (a.get('autocomplete') or '').lower().split() if t in AUTOCOMPLETE)}
 a=root.attributes or {};parts=[]
 if root.tag in ['body','html']:
  return {'context':'','fields':[hint(el) for el in elements]}
 for marker,source in [('heading',' '.join(text(n) for n in headings if visible(n))),('identifier',' '.join([a.get('name') or '',a.get('id') or '',a.get('aria-label') or ''])),('description',' '.join(text(n) for n in root.css('legend,p,[role=heading]')[:8] if visible(n))),('group',' '.join(text(n) for n in root.css('button') if visible(n)))]:
  value=sanitize(source,160)
  if value:parts.extend([marker,value])
 cursor=root
 for _ in range(2):
  sibling=cursor.prev
  # At most two neighboring non-control text blocks, never the entire parent page.
  for _ in range(3):
   if sibling is None:break
   if sibling.tag.startswith('-'):
    sibling=sibling.prev;continue
   if sibling.tag in ['p','legend','small'] and not sibling.css('input,textarea,select') and visible(sibling):
    value=sanitize(text(sibling),128)
    if value:parts.extend(['description',value])
   elif sibling.tag=='form' or sibling.css('form'):break
   sibling=sibling.prev
  if cursor.parent is None or cursor.parent.tag in ['body','html']:break
  cursor=cursor.parent
 context=' '.join(parts)
 if len(context)>512:context=context[:512].rsplit(' ',1)[0]
 return {'context':context,'fields':[hint(el) for el in elements]}
