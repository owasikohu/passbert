import tempfile
import unittest
from passbert.data import extract, generate, serialize

class DataTests(unittest.TestCase):
    def test_secrets_and_executable_content(self):
        form=extract('''<form action="https://secret.example/?token=PRIVATE"><h2>ログイン</h2><script>password PRIVATE</script><label for="u">メール PRIVATE</label><input id="u" value="PRIVATE" data-token="PRIVATE"><input type="password" value="PRIVATE"><textarea>PRIVATE</textarea><input type="hidden" value="PRIVATE"></form>''')[0]
        text=serialize(form)
        self.assertNotIn('PRIVATE',str(form)); self.assertNotIn('secret',str(form)); self.assertEqual(len(form['fields']),3)
        self.assertIn('メール',text)
    def test_nested_textarea(self):
        self.assertNotIn('password',str(extract('<form><label><textarea>password</textarea></label></form>')))
    def test_context_excludes_controls(self):
        form=extract('<form><h2>login<textarea>password</textarea></h2><input></form>')[0]
        self.assertEqual(form['context'],'login')

    def test_splits(self):
        with tempfile.TemporaryDirectory() as root:
            rows=generate(root,60)
            for key in ['site_id','signature','template_family']:
                sets=[{r[key] for r in data} for data in rows.values()]
                for i in range(3):
                    for j in range(i): self.assertFalse(sets[i]&sets[j])
            for data in rows.values():
                self.assertTrue(data)
                for row in data: self.assertEqual(len(row['form']['fields']),len(row['field_labels']))
    def test_hidden_and_formless(self):
        self.assertEqual(len(extract('<input aria-hidden="true"><input type="hidden"><input placeholder="email">')[0]['fields']),1)

if __name__=='__main__': unittest.main()
