import unittest
from passbert.context_v3 import sanitize, render, VERSION
from passbert.fast_extract import extract_fast
from passbert.review import valid_view

class ContextTests(unittest.TestCase):
 def test_boundaries_and_identifiers(self):
  self.assertEqual(sanitize('painting spring backup'), '')
  self.assertEqual(sanitize('firstName_userID'), 'first name user id')
  self.assertEqual(sanitize('Ｓｉｇｎ ｉｎ'), 'sign in')
 def test_sources_and_private_control_text(self):
  html='''<h1>Register</h1><form><fieldset><legend>Account</legend>
  <label for="username">姓</label><input id="username" aria-describedby="help" value="password">
  <p id="help">Required family name</p></fieldset>
  <textarea>password</textarea><select><option>password</option></select>
  <p hidden>password</p><div contenteditable>password</div></form>'''
  baseline,_=extract_fast(html)
  same,views=extract_fast(html,annotation_builder=render)
  self.assertEqual(baseline,same)
  view=views[0]
  self.assertIn('label family name',view['fields'][0]['hint'])
  self.assertIn('identifier username',view['fields'][0]['hint'])
  self.assertIn('description required family name',view['fields'][0]['hint'])
  self.assertNotIn('password',str(view))
  self.assertTrue(valid_view(view,VERSION))
  self.assertFalse(valid_view(view,'unknown'))
 def test_orphan_does_not_inherit_global_heading(self):
  _,views=extract_fast('<h1>Reset password</h1><input>',annotation_builder=render)
  self.assertEqual(views[0]['context'],'')

if __name__=='__main__':unittest.main()
