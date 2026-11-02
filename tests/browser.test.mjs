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
