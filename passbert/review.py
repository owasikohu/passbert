"""Blind review contracts and strict label-only output validation."""
import json
import re
from passbert.annotation import TERMS,AUTOCOMPLETE

FORM_LABELS=['login','signup','password-change','password-recovery','otp','payment','address','newsletter','contact','search','other','unreviewable']
FIELD_LABELS=AUTOCOMPLETE+['unreviewable']
TEACHER='Qwen/Qwen3.8-27B'
REVISION='4ca720788d1e01f1bff70c033e0d0028fd02e502'
SYSTEM='''You label privacy-filtered web form descriptors in English and Japanese.
Return only JSON with exactly these keys: "form_label" and "field_labels".
Return exactly one field label for EVERY field in the supplied order. Never drop fields.
Form labels: '''+', '.join(FORM_LABELS)+'''.
Field labels: '''+', '.join(FIELD_LABELS)+'''.
Rules:
- username: identifier accepting username/user ID or a mix such as email or username. email: email-only.
- current-password: existing secret. new-password: a secret being created/reset, including confirmation.
- A password input alone does not distinguish current-password from new-password.
- one-time-code: OTP/verification, including each split box. captcha: challenge answer, not OTP.
- name is full name; given-name/family-name are first/last names. Use name if unspecified.
- password-recovery is requesting a reset; password-change sets or changes the password.
- other means evidence of a purpose/field outside the listed classes. It does not mean uncertainty.
- Use unreviewable for any form or field lacking enough evidence. It is OK for purpose to be unreviewable while a field is clear.
- Descriptors are noisy keyword fragments, not original sentences. Repetition is not stronger evidence.
- Isolated "in", "up", or generic next/continue buttons are insufficient to establish login/signup.
- autocomplete is a fallible hint. Look for corroborating evidence; do not blindly trust it.
- Classify what is described. Do not invent missing page context or assume every form is authentication.
No explanations, code fences, confidence scores, record IDs, or extra keys.'''

def valid_view(form):
    if not isinstance(form,dict) or set(form)!={'context','fields'}:return False
    if not isinstance(form['fields'],list) or not 1<=len(form['fields'])<=64:return False
    values=[form['context']]
    for field in form['fields']:
        if not isinstance(field,dict) or set(field)!={'type','hint','autocomplete'}:return False
        if field['type'] not in ['text','email','password','tel','number','search','url']:return False
        if not isinstance(field['autocomplete'],str) or any(t not in AUTOCOMPLETE for t in field['autocomplete'].split()):return False
        values.append(field['hint'])
    for value in values:
        if not isinstance(value,str) or len(value)>256:return False
        tokens=[t.replace('ı','i').replace('i\u0307','i').replace('ſ','s') for t in value.split()]
        for i,token in enumerate(tokens):
            if token not in TERMS and not (i==len(tokens)-1 and len(value)==256 and any(t.startswith(token) for t in TERMS)):return False
    return True

def blind_payload(request,train_record):
    if train_record.get('split')!='train' or train_record.get('evaluation_only'):raise ValueError('Reserved/evaluation records cannot be reviewed by the training teacher')
    if request.get('teacher_predictions_visible') is not False:raise ValueError('Review must be blind')
    if request['record_id']!=train_record['record_id'] or not re.fullmatch('[a-f0-9]{64}',request['record_id']):raise ValueError('Record identity mismatch')
    if request['form']!=train_record.get('annotation_view',train_record['form']) or not valid_view(request['form']):raise ValueError('Unsafe or mismatched descriptors')
    return {'record_id':request['record_id'],'language':request['language'],'form':request['form'],'kind':'corpus'}

def messages(request):
    if not valid_view(request['form']):raise ValueError('Unsafe view')
    payload={'field_count':len(request['form']['fields']),'form':request['form']}
    return [{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}]

def parse_labels(text,field_count):
    text=text.strip()
    if text.startswith('```'):
        lines=text.splitlines()
        if len(lines)>=3 and lines[-1].strip()=='```':text='\n'.join(lines[1:-1])
    try:value=json.loads(text)
    except (ValueError,TypeError):raise ValueError('invalid_json') from None
    if not isinstance(value,dict) or set(value)!={'form_label','field_labels'}:raise ValueError('invalid_schema')
    if value['form_label'] not in FORM_LABELS:raise ValueError('invalid_form_label')
    labels=value['field_labels']
    if not isinstance(labels,list) or len(labels)!=field_count:raise ValueError('field_alignment_mismatch')
    if any(not isinstance(label,str) or label not in FIELD_LABELS for label in labels):raise ValueError('invalid_field_label')
    return value
