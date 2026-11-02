"""Generate or check the shared Python/DOM privacy vocabulary."""
import argparse
import json
from pathlib import Path
from passbert.data import WORDS,FIELDS,FORMS
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
text='export const words = '+json.dumps(WORDS,ensure_ascii=False)+';\nexport const fieldLabels = '+json.dumps(FIELDS)+';\nexport const formLabels = '+json.dumps(FORMS)+';\n'
path=Path('web/policy.mjs')
if args.check:
    assert path.read_text()==text, 'Run python -m scripts.sync_policy'
else: path.write_text(text)
