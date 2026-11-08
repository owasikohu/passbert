"""Expanded closed semantic vocabulary for labeling; arbitrary strings are never retained."""
import re
from passbert.data import WORDS
VERSION='semantic-annotation-v2'
TERMS=sorted(set(WORDS+['account','identifier','member','log','signin','signup','forgot','recovery','change','repeat','pin','security','auth','verify','subscribe','newsletter','checkout','payment','address','first','last','name','given','family','organization','company','street','city','state','region','postal','zip','country','phone','telephone','mobile','number','card','credit','expiry','expiration','month','year','cvv','cvc','birthday','birth','captcha','message','subject','comment','quantity','coupon','username','email','アカウント','会員','氏名','姓','名','住所','郵便番号','電話','携帯','生年月日','支払い','クレジット','カード','有効期限','セキュリティ','暗証番号','変更','再入力','忘れ','復旧','ログオン','サインイン','サインアップ','メールアドレス','購読','お知らせ','送信','件名','お問い合わせ']),key=lambda x:(-len(x),x))
PATTERN=re.compile('|'.join(map(re.escape,TERMS)),re.I)
AUTOCOMPLETE=['username','email','current-password','new-password','one-time-code','tel','name','given-name','family-name','organization','street-address','address-line2','address-level2','address-level1','postal-code','country','cc-name','cc-number','cc-exp','cc-exp-month','cc-exp-year','cc-csc','bday','search','captcha','other']
def sanitize(text):return ' '.join(match.group().lower() for match in PATTERN.finditer(str(text)[:2048]))[:256]
