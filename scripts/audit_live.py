"""Read-only, isolated Firefox audit; selector contracts are silver labels, not human ground truth."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from passbert.inference import Classifier
from passbert.metrics import score
from passbert.data import FORMS,FIELDS

p=argparse.ArgumentParser();p.add_argument('--model',default='artifacts/kaggle-output/model');p.add_argument('--output',default='artifacts/live-baseline.json');p.add_argument('--firefox',default='artifacts/firefox-runtime/firefox/firefox');args=p.parse_args()
os.environ.setdefault('SE_CACHE_PATH',str(Path('artifacts/selenium').resolve()))
options=webdriver.FirefoxOptions();options.binary_location=str(Path(args.firefox).resolve());options.add_argument('-headless');options.page_load_strategy='eager';options.set_preference('signon.rememberSignons',False)
model=Classifier(args.model);driver=webdriver.Firefox(options=options);driver.set_page_load_timeout(30)
script=Path('artifacts/firefox-extension/capture.js').read_text()
# Test contracts defined before running any model predictions. No DOM/HTML/screenshots saved.
contract='''const state=globalThis.__passbertEvaluation;return arguments[0].map(spec=>{const matches=[...document.querySelectorAll(spec.selector)];if(matches.length!==1)return null;const el=matches[0];for(let i=0;i<state.groups.length;i++){const j=state.groups[i].indexOf(el);if(j>=0)return {form:i,field:j};}return null;});'''
report={'scope':'live selector-contract smoke, nonrepresentative silver labels; no human audit; evaluation_only','sites':[]}
try:
 for spec in json.loads(Path('tests/live-sites.json').read_text()):
    item={'site':spec['name'],'language':spec['language'],'status':'unavailable'}
    try:
        try:driver.get(spec['url'])
        except Exception:pass
        if driver.execute_script('return location.hostname')!=urlparse(spec['url']).hostname:
            item['status']='unexpected_redirect';raise ValueError('Unexpected redirect')
        WebDriverWait(driver,12).until(lambda d:d.execute_script('return document.querySelectorAll("input:not([type=hidden])").length')>0)
        combined='const capture='+script.rstrip().rstrip(';')+';const mapping=(()=>{'+contract+'})();return {capture,mapping};'
        result=driver.execute_script(combined,spec['fields']);capture=result['capture'];mapping=result['mapping']
        item.update({'forms_extracted':len(capture['forms']),'fields_extracted':sum(len(f['fields']) for f in capture['forms']),'expected_fields':len(mapping),'contract_fields_found':sum(m is not None for m in mapping)})
        if any(m is None for m in mapping):item['status']='contract_mismatch'
        elif len({m['form'] for m in mapping})!=1:item['status']='grouping_mismatch'
        else:
            i=mapping[0]['form'];form=capture['forms'][i]
            if any(not capture['visibility'][m['form']][m['field']] for m in mapping):item['status']='contract_hidden'
            else:
                labels=['unreviewable']*len(form['fields'])
                for m,s in zip(mapping,spec['fields']):labels[m['field']]=s['label']
                start=time.perf_counter();pred=model.predict(form)
                item.update({'status':'scored','site_id':'host-sha256:'+hashlib.sha256(urlparse(spec['url']).hostname.encode()).hexdigest(),'form':form,'form_label':spec['purpose'],'field_labels':labels,'prediction':pred,'latency_ms':(time.perf_counter()-start)*1000})
    except Exception as e:
        item['error_type']=type(e).__name__
    report['sites'].append(item);print(spec['name'],item['status'],flush=True)
finally:driver.quit()
yt=[];yp=[];ft=[];fp=[]
for item in report['sites']:
 if item['status']=='scored':
    yt.append(item['form_label']);yp.append(item['prediction']['form'])
    for a,b in zip(item['field_labels'],item['prediction']['fields']):
        if a!='unreviewable':ft.append(a);fp.append(b)
report['summary']={'accuracy_available':bool(yt),'attempted':len(report['sites']),'scored':len(yt),'form':score(yt,yp,FORMS) if yt else None,'field':score(ft,fp,FIELDS) if ft else None}
Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report['summary'],ensure_ascii=False))
