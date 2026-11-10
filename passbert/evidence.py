"""Conservative review routing. Passing a rule is evidence, never ground truth."""
import re
from passbert.review import parse_labels, valid_view
import json

VERSION='evidence-routing-v1'
PASSWORD={'current-password','new-password'}
SENSITIVE=PASSWORD|{'one-time-code','captcha'}

def words(value):
 return set(re.findall(r'[a-z]+',value.lower()))

def assess(form, labels, policy='semantic-context-v3'):
 if not valid_view(form,policy):raise ValueError('Unsafe descriptors')
 labels=parse_labels(json.dumps(labels),len(form['fields']))
 context=words(form['context']);flags=[]
 for field,label in zip(form['fields'],labels['field_labels']):
  hint=words(field['hint']);ac=set(field['autocomplete'].split());reasons=[]
  if label=='unreviewable':reasons.append('abstained')
  if label in PASSWORD:
   # autocomplete alone can be set on unrelated anti-bot inputs.
   if field['type']!='password' and not hint.intersection({'password','pwd'}):reasons.append('password_evidence_missing')
   if ac.intersection(PASSWORD-{label}):reasons.append('password_autocomplete_conflict')
   if label=='new-password' and not (hint|context).intersection({'new','create','register','signup','reset','repeat','confirm','change'}):reasons.append('new_password_role_missing')
   if label=='current-password' and not (hint|context).intersection({'current','old','existing','login','log','signin','unsubscribe'}):
    if not ('sign' in (hint|context) and 'in' in (hint|context)):reasons.append('current_password_role_missing')
  if label=='one-time-code':
   if not hint.intersection({'otp','verification','sms'}) and not {'one','time'}.issubset(hint):reasons.append('otp_evidence_missing')
   if 'captcha' in hint or {'image','code'}.issubset(hint):reasons.append('otp_captcha_conflict')
  if label=='captcha':
   if not hint.intersection({'captcha','challenge'}) and not {'image','code'}.issubset(hint):reasons.append('captcha_evidence_missing')
   if hint.intersection({'otp','sms'}):reasons.append('captcha_otp_conflict')
  flags.append(reasons)
 purpose=[]
 if labels['form_label']=='unreviewable':purpose.append('abstained')
 if labels['form_label'] in {'login','signup','password-change','otp'}:
  if any(r for label,r in zip(labels['field_labels'],flags) if label in SENSITIVE):purpose.append('sensitive_field_needs_review')
 return {'policy':VERSION,'field_flags':flags,'form_flags':purpose,
         'route':'manual_review' if purpose or any(flags) else 'weak_candidate',
         'verified':False,'training_eligible':False}
