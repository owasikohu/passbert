"""Optional real Firefox smoke test. Requires selenium and Firefox (not project runtime deps)."""
import argparse
import os
import json
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait,Select

p=argparse.ArgumentParser();p.add_argument('--firefox',default='artifacts/firefox-runtime/firefox/firefox');p.add_argument('--automatic',action='store_true');p.add_argument('--long',action='store_true');args=p.parse_args()
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers()
        if args.long:
            self.wfile.write(('<!doctype html><meta charset="utf-8"><form><h2>認証 コード</h2>'+''.join('<input autocomplete="one-time-code" placeholder="認証 コード" value="SECRET_SENTINEL">' for _ in range(64))+'<button>確認</button></form>').encode());return
        self.wfile.write('<!doctype html><html lang="ja"><meta charset="utf-8"><form><h2>ログイン</h2><label for="email">メール</label><input id="email" type="email" autocomplete="email" value="PRIVATE_SENTINEL"><label for="pw">パスワード</label><input id="pw" type="password" autocomplete="current-password" value="SECRET_SENTINEL"><button>ログイン</button></form>'.encode())
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
os.environ.setdefault('SE_CACHE_PATH',str(Path('artifacts/selenium').resolve()))
opts=webdriver.FirefoxOptions();opts.binary_location=str(Path(args.firefox).resolve());opts.add_argument('-headless');
opts.set_preference('browser.aboutwelcome.enabled',False)
opts.set_preference('datareporting.policy.dataSubmissionEnabled',False)
opts.set_preference('toolkit.telemetry.enabled',False)
from selenium.webdriver.firefox.service import Service
driver=webdriver.Firefox(options=opts,service=Service(service_args=['--allow-system-access']))
try:
    driver.install_web_extension(str(Path('artifacts/passbert-firefox-eval.xpi').resolve()),permanent=False)
    driver.get(f'http://127.0.0.1:{server.server_port}/?token=URL_SENTINEL')
    original=driver.current_window_handle
    driver.set_context('chrome')
    buttons=driver.execute_script("return [...document.querySelectorAll('[id*=passbert]')].map(el=>el.id)")
    Path('artifacts/firefox-buttons.json').write_text(json.dumps(buttons))
    driver.find_element(By.ID,'unified-extensions-button').click()
    Path('artifacts/firefox-panel.html').write_text(driver.execute_script("return document.getElementById('unified-extensions-panel').outerHTML"))
    button=WebDriverWait(driver,10).until(lambda d:d.find_element(By.ID,'passbert-eval_owasikohu-BAP'))
    button.click()
    driver.set_context('content')
    WebDriverWait(driver,30).until(lambda d:len(d.window_handles)>1)
    driver.switch_to.window(next(h for h in driver.window_handles if h!=original))
    WebDriverWait(driver,30).until(lambda d:len(d.find_elements(By.CSS_SELECTOR,'#forms select'))==(65 if args.long else 3))
    selects=driver.find_elements(By.CSS_SELECTOR,'#forms select')
    expected_fields=['one-time-code']*64 if args.long else ['email','current-password']
    if args.automatic:
        driver.find_element(By.ID,'automatic').click()
        WebDriverWait(driver,90).until(lambda d:'自動診断を保存しました' in d.find_element(By.ID,'status').text)
    else:
        for el,label in zip(selects,(['otp'] if args.long else ['login'])+expected_fields):Select(el).select_by_value(label)
        driver.find_element(By.ID,'predict').click()
        WebDriverWait(driver,90).until(lambda d:d.find_element(By.ID,'save').is_enabled())
        driver.find_element(By.ID,'save').click()
        WebDriverWait(driver,10).until(lambda d:'保存しました' in d.find_element(By.ID,'status').text)
    records=driver.execute_async_script('const done=arguments[0];browser.storage.local.get("records").then(done);')
    text=json.dumps(records)
    assert all(secret not in text for secret in ['PRIVATE_SENTINEL','SECRET_SENTINEL','URL_SENTINEL'])
    assert len(records['records'])==1
    assert records['records'][0]['rows'][0]['field_labels']==(['unreviewable']*len(expected_fields) if args.automatic else expected_fields)
    assert records['records'][0]['rows'][0]['prediction']['fields']==expected_fields
    assert all(not el.is_enabled() for el in selects)
    assert 'raw_model' in records['records'][0]['rows'][0]['prediction']
    if args.long:assert records['records'][0]['rows'][0]['prediction']['windows']>1
    if args.automatic:assert records['records'][0]['annotation_protocol']=='automated-unlabeled-smoke'
    report={'firefox':driver.capabilities['browserVersion'],'status':driver.find_element(By.ID,'status').text,'timing':driver.find_element(By.ID,'timing').text,'record':records['records'][0]}
    Path('artifacts/firefox-smoke'+('-long' if args.long else '-auto' if args.automatic else '')+'.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    driver.save_screenshot('artifacts/firefox-review.png')
    driver.find_element(By.ID,'locate').click()
    driver.switch_to.window(original)
    WebDriverWait(driver,10).until(lambda d:d.find_elements(By.CSS_SELECTOR,'[data-passbert-overlay]'))
    if not args.long:
        assert driver.find_element(By.ID,'pw').get_property('value')=='SECRET_SENTINEL'
        assert driver.find_element(By.ID,'email').get_property('value')=='PRIVATE_SENTINEL'
    print(json.dumps({'firefox':report['firefox'],'timing':report['timing'],'status':'PASS'},ensure_ascii=False))
finally:
    driver.quit();server.shutdown()
