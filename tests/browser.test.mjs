import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { JSDOM } from 'jsdom';
import { extract } from '../web/extract.mjs';
import { load } from '../web/infer.mjs';
test('Python and DOM extraction share fixtures',()=>{
 for(const fixture of JSON.parse(fs.readFileSync('tests/extraction-fixtures.json','utf8'))) assert.deepEqual(extract(new JSDOM(fixture.html).window.document),fixture.expected);
});
test('WordPiece matches Python on every synthetic test form',{skip:!fs.existsSync('artifacts/tokenizer-fixtures.json')},async()=>{
 const oldFetch=globalThis.fetch;
 try {
 globalThis.fetch=async()=>({json:async()=>JSON.parse(fs.readFileSync('artifacts/smoke/tokenizer.json','utf8'))});
 const model=await load({InferenceSession:{create:async()=>({})}},'unused');
 for(const f of JSON.parse(fs.readFileSync('artifacts/tokenizer-fixtures.json','utf8'))) assert.deepEqual(model.encode(f.text),f.ids);
 }finally{globalThis.fetch=oldFetch;}
});
test('ORT Web WASM int8 labels match test references',{skip:!fs.existsSync('artifacts/smoke/model.int8.onnx')},async()=>{
 const ort=await import('onnxruntime-web'); ort.env.wasm.numThreads=1;
 const oldFetch=globalThis.fetch;
 try{
 globalThis.fetch=async()=>({json:async()=>JSON.parse(fs.readFileSync('artifacts/smoke/tokenizer.json','utf8'))});
 const model=await load({...ort,InferenceSession:{create:(_path,options)=>ort.InferenceSession.create(new Uint8Array(fs.readFileSync('artifacts/smoke/model.int8.onnx')),options)}},'unused');
 const rows=fs.readFileSync('artifacts/data/test.jsonl','utf8').trim().split('\n').map(JSON.parse);
 for(const row of rows){const result=await model.predict(row.form);assert.equal(result.form,row.form_label);assert.deepEqual(result.fields,row.field_labels);}
 }finally{globalThis.fetch=oldFetch;}
});
test('Python/DOM parity for independent robustness cases',()=>{
 for(const fixture of JSON.parse(fs.readFileSync('tests/robustness.json','utf8'))) assert.deepEqual(extract(new JSDOM(fixture.html).window.document),fixture.expected);
});
test('whole-field windows preserve 64 fields and repeated context',async()=>{
 const oldFetch=globalThis.fetch;
 try{
 globalThis.fetch=async()=>({json:async()=>({model:{vocab:{'[PAD]':0,'[UNK]':1,'[CLS]':2,'[FLD]':5,'login':6,'password':7,'current':8,'-':9}}})});
 const model=await load({InferenceSession:{create:async()=>({})}},'unused');
 const form={context:'login',fields:Array.from({length:64},()=>({type:'password',hint:'current password '.repeat(8),autocomplete:'current-password'}))};
 const chunks=model.windows(form);assert(chunks.length>1);assert.deepEqual(chunks.flatMap(c=>c.indices),Array.from({length:64},(_,i)=>i));
 for(const chunk of chunks){assert(chunk.ids.length<=256);assert.equal(chunk.ids[0],model.encode('[CLS]')[0]);assert.equal(chunk.positions.length,chunk.indices.length);}
 }finally{globalThis.fetch=oldFetch;}
});
test('attribute guards retain raw model labels and explain corrections',async()=>{
 const {guard}=await import('../web/decision.mjs');
 for(const c of JSON.parse(fs.readFileSync('tests/decision-contracts.json','utf8'))){
  const raw={form:c.purpose,fields:[c.raw]};const corrected=guard({fields:[c.field]},raw);
  assert.equal(corrected.fields[0],c.expected);assert.equal(corrected.guard_reasons[0],c.reason);assert.deepEqual(raw,{form:c.purpose,fields:[c.raw]});assert.deepEqual(corrected.raw_model,raw);
 }
});
test('candidate model Python/ORT Web token windows and labels match',{skip:!fs.existsSync('artifacts/automation/parity.json')},async()=>{
 const fixture=JSON.parse(fs.readFileSync('artifacts/automation/parity.json','utf8'));const ort=await import('onnxruntime-web');ort.env.wasm.numThreads=1;
 const oldFetch=globalThis.fetch;
 try{
 globalThis.fetch=async()=>({json:async()=>JSON.parse(fs.readFileSync(fixture.model+'/tokenizer.json','utf8'))});
 const model=await load({...ort,InferenceSession:{create:(_path,options)=>ort.InferenceSession.create(new Uint8Array(fs.readFileSync(fixture.model+'/model.int8.onnx')),options)}},'unused');
 for(const c of fixture.cases){assert.deepEqual(model.windows(c.form),c.windows);const p=await model.predict(c.form);assert.equal(p.form,c.prediction.form);assert.deepEqual(p.fields,c.prediction.fields);}
 }finally{globalThis.fetch=oldFetch;}
});
