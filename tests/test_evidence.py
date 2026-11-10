import unittest
from passbert.evidence import assess

class EvidenceTests(unittest.TestCase):
 def check(self,field,label,context=''):
  return assess({'context':context,'fields':[{'type':'text','hint':'','autocomplete':'',**field}]},{'form_label':'other','field_labels':[label]})
 def test_autocomplete_alone_cannot_establish_password(self):
  r=self.check({'autocomplete':'new-password'},'new-password')
  self.assertIn('password_evidence_missing',r['field_flags'][0])
  self.assertFalse(r['training_eligible'])
 def test_generic_code_cannot_establish_otp_or_captcha(self):
  for label,reason in [('one-time-code','otp_evidence_missing'),('captcha','captcha_evidence_missing')]:
   self.assertIn(reason,self.check({'hint':'identifier code'},label)['field_flags'][0])
 def test_password_requires_role_and_detects_conflict(self):
  self.assertIn('current_password_role_missing',self.check({'type':'password'},'current-password')['field_flags'][0])
  self.assertIn('password_autocomplete_conflict',self.check({'type':'password','autocomplete':'new-password'},'current-password','heading login')['field_flags'][0])
 def test_supported_sensitive_fields_remain_weak(self):
  cases=[({'type':'password'},'current-password','heading login'),({'type':'password','hint':'label confirm password'},'new-password',''),({'hint':'label sms verification code'},'one-time-code',''),({'hint':'identifier captcha'},'captcha','')]
  for field,label,context in cases:
   r=self.check(field,label,context);self.assertEqual(r['route'],'weak_candidate');self.assertFalse(r['verified']);self.assertFalse(r['training_eligible'])
 def test_unsafe_view_and_misalignment_rejected(self):
  with self.assertRaises(ValueError):self.check({'hint':'PRIVATE_SENTINEL'},'other')
  with self.assertRaises(ValueError):assess({'context':'','fields':[{'type':'text','hint':'','autocomplete':''}]},{'form_label':'other','field_labels':[]})
