import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {JSDOM} from 'jsdom';
import {makeRecord,metrics} from '../extension/firefox/evaluation.mjs';
const form={context:'login',fields:[{type:'password',hint:'password',autocomplete:''}]};
const snapshot={id:'id',site_id:'host-sha256:abc',forms:[form],visibility:[[true]],extraction_ms:1,captured_at:'2026-10-30'};
test('evaluation labels align, unreviewable and failed predictions are excluded',()=>{
 const record=makeRecord(snapshot,[{form_label:'login',field_labels:['current-password']}],[{form:'login',fields:['new-password'],model_ms:1}],'ja',{sha256:'test'});
 assert.deepEqual(metrics([record]),{form:{correct:1,total:1},field:{correct:0,total:1}});
 assert.throws(()=>makeRecord(snapshot,[{form_label:'',field_labels:['']}],[null],'ja',{}));
 assert.throws(()=>makeRecord(snapshot,[{form_label:'login',field_labels:[]}],[null],'ja',{}));
 assert.throws(()=>makeRecord(snapshot,[{form_label:'login',field_labels:['current-password']}],[{form:'login',fields:[]}],'ja',{}));
 const skipped=makeRecord(snapshot,[{form_label:'unreviewable',field_labels:['unreviewable']}],[null],'ja',{});
 assert.deepEqual(metrics([skipped]),{form:{correct:0,total:0},field:{correct:0,total:0}});
});
test('packaged capture excludes values and URLs, retains DOM mapping only in isolated world',{skip:!fs.existsSync('artifacts/firefox-extension/capture.js')},()=>{
 const dom=new JSDOM('<form><h2>ログイン</h2><label for="u">メール</label><input id="u" value="PRIVATE"><input type="password" value="SECRET"><textarea>PRIVATE</textarea><input type="hidden" value="SECRET"></form>',{url:'https://test.example/private?token=SECRET',runScripts:'outside-only'});
 const {window}=dom;
 Object.defineProperty(window.document,'cookie',{get(){throw Error('Cookie must not be read');}});
 Object.defineProperty(window.HTMLInputElement.prototype,'value',{get(){throw Error('Input value must not be read');}});
 Object.defineProperty(window.HTMLTextAreaElement.prototype,'value',{get(){throw Error('Textarea value must not be read');}});
 window.HTMLElement.prototype.getBoundingClientRect=()=>({width:100,height:20});
 const result=window.eval(fs.readFileSync('artifacts/firefox-extension/capture.js','utf8'));
 const serialized=JSON.stringify(result);
 assert(!serialized.includes('PRIVATE'));assert(!serialized.includes('SECRET'));assert(!serialized.includes('/private'));
 assert.equal(result.forms[0].fields.length,3);assert.equal(result.visibility[0].length,3);
 assert.equal(window.__passbertEvaluation.groups[0][1].type,'password');
 const first=result.snapshot_key;const next=window.eval(fs.readFileSync('artifacts/firefox-extension/capture.js','utf8'));assert.notEqual(next.snapshot_key,first);
});
test('manifest grants access only on user action and keeps resources internal',()=>{
 const m=JSON.parse(fs.readFileSync('extension/firefox/manifest.json','utf8'));
 assert(m.permissions.includes('activeTab'));assert(!m.host_permissions);assert(!m.content_scripts);assert(!m.web_accessible_resources);
 assert(m.content_security_policy.extension_pages.includes("connect-src 'self'"));
});
