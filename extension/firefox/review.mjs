import * as ort from './vendor/ort.wasm.min.mjs';
import { load } from './web/infer.mjs';
import { fieldLabels,formLabels } from './web/policy.mjs';
import { metrics,makeRecord,UNREVIEWABLE } from './evaluation.mjs';
const $=id=>document.getElementById(id);
const id=new URL(location.href).searchParams.get('id');
const snapshot=(await browser.storage.session.get(id))[id];
let predictions=null,metadata=null,model=null;const annotations=[];
function select(labels,change){const s=document.createElement('select');for(const [value,text] of [['','選択してください'],...labels.map(x=>[x,x]),[UNREVIEWABLE,'判定不能 / 対象外']]){const o=document.createElement('option');o.value=value;o.textContent=text;s.append(o);}s.onchange=()=>{change(s.value);$('save').disabled=true;};return s;}
function cell(row,text){const td=document.createElement('td');td.textContent=text;row.append(td);return td;}
async function refresh(){const {records=[]}=await browser.storage.local.get('records');const m=metrics(records);$('summary').textContent=`保存 ${records.length} ページ / フォーム ${m.form.correct}/${m.form.total} / 入力欄 ${m.field.correct}/${m.field.total} 正解（判定不能・推論失敗を除外）`;}
if(!snapshot||snapshot.error){$('status').textContent=snapshot?.error||'評価データがありません。対象ページで拡張ボタンを押してください。';}
else{
 $('status').textContent=`${snapshot.forms.length} フォーム抽出。対象はクリック時点のトップフレームです。`; $('controls').hidden=!snapshot.forms.length;
 snapshot.forms.forEach((form,i)=>{
  const a={form_label:'',field_labels:form.fields.map(()=> '')};annotations.push(a);
  const section=document.createElement('article');section.className='form';const h=document.createElement('h2');h.textContent=`F${i+1}`;section.append(h);
  const context=document.createElement('p');context.textContent='文脈: '+(form.context||'（情報なし）');section.append(context);
  section.append(select(formLabels,x=>a.form_label=x));const pred=document.createElement('span');pred.id=`form-pred-${i}`;section.append(pred);
  const table=document.createElement('table');const header=document.createElement('tr');['入力欄','抽出した分類情報','正解','予測'].forEach(x=>{const th=document.createElement('th');th.textContent=x;header.append(th);});table.append(header);
  form.fields.forEach((f,j)=>{const tr=document.createElement('tr');cell(tr,`${i+1}.${j+1}${snapshot.visibility[i][j]?'':'（非表示）'}`);cell(tr,[f.type,f.hint,f.autocomplete].join(' / '));const td=document.createElement('td');td.append(select(fieldLabels,x=>a.field_labels[j]=x));tr.append(td);cell(tr,'未推論').id=`field-pred-${i}-${j}`;table.append(tr);});section.append(table);$('forms').append(section);
 });
}
$('predict').onclick=async()=>{
 try{
 if(annotations.some(a=>!a.form_label||a.field_labels.some(x=>!x)))throw Error('予測を見る前に全ラベルを選択してください（判定不能も選べます）。');
 document.querySelectorAll('#forms select').forEach(s=>s.disabled=true);
 $('predict').disabled=true;$('status').textContent='モデル準備・CPU推論中…';
 const cold=performance.now();ort.env.wasm.numThreads=1;ort.env.wasm.proxy=false;ort.env.wasm.wasmPaths=browser.runtime.getURL('vendor/');
 if(!model){model=await load(ort,browser.runtime.getURL('model'));metadata=await (await fetch('model/metadata.json')).json();}
 const ready=performance.now();predictions=[];let errors=0;let modelTime=0;
 for(let i=0;i<snapshot.forms.length;i++){
  let result=null;try{result=await model.predict(snapshot.forms[i]);modelTime+=result.model_ms;}catch{errors++;}
  predictions.push(result);const p=$(`form-pred-${i}`);p.textContent=result?' 予測: '+result.form:' 推論不可（長さ制限など）';p.className=result?.form===annotations[i].form_label?'correct':'wrong';
  snapshot.forms[i].fields.forEach((_,j)=>{const td=$(`field-pred-${i}-${j}`);td.textContent=result?.fields[j]||'推論不可';td.className=result?.fields[j]===annotations[i].field_labels[j]?'correct':'wrong';});
 }
 $('timing').textContent=`抽出 ${snapshot.extraction_ms.toFixed(1)} ms / モデル準備 ${(ready-cold).toFixed(1)} ms / 推論合計 ${modelTime.toFixed(1)} ms（WASM 1 thread、初回warmupなし）`;
 $('status').textContent=`推論完了。失敗 ${errors} フォーム。正解ラベルは予測表示後に固定します。やり直す場合は元ページで再抽出してください。`;$('save').disabled=false;document.querySelectorAll('#forms select').forEach(s=>s.disabled=true);
 }catch(e){$('status').textContent=e.message;}finally{$('predict').disabled=false;}
};
$('save').onclick=async()=>{try{const record=makeRecord(snapshot,annotations,predictions,$('language').value,metadata);const {records=[]}=await browser.storage.local.get('records');const kept=records.filter(r=>r.snapshot_id!==id);if(kept.length>=300)throw Error('保存上限300ページです。書き出して削除してください。');kept.push(record);await browser.storage.local.set({records:kept});$('status').textContent='端末に保存しました。';await refresh();}catch(e){$('status').textContent=e.message;}};
$('language').onchange=()=>{$('save').disabled=!predictions;};
$('locate').onclick=async()=>{try{
 await browser.scripting.executeScript({target:{tabId:snapshot.tabId},args:[snapshot.snapshot_key],func:(key)=>{
 const state=globalThis.__passbertEvaluation;if(!state||state.key!==key)throw Error('ページが変わっています。再抽出してください。');
 state.overlay?.remove();const host=document.createElement('div');host.setAttribute('data-passbert-overlay',key);const shadow=host.attachShadow({mode:'closed'});host.style.cssText='position:fixed;inset:0;z-index:2147483647;pointer-events:none';
 for(const [i,fields] of state.groups.entries())for(const [j,el]of fields.entries()){if(!el.isConnected)continue;const r=el.getBoundingClientRect();if(!r.width||!r.height)continue;const box=document.createElement('div');box.textContent=`F${i+1} / ${i+1}.${j+1}`;box.style.cssText=`position:fixed;left:${r.left}px;top:${r.top}px;width:${r.width}px;height:${r.height}px;outline:2px solid #e02965;color:#fff;font:12px sans-serif;background:#e0296520;`;const badge=document.createElement('span');badge.textContent=box.textContent;badge.style.cssText='background:#a00037;color:white';box.textContent='';box.append(badge);shadow.append(box);}document.documentElement.append(host);state.overlay=host;setTimeout(()=>host.remove(),15000);
 }});await browser.tabs.update(snapshot.tabId,{active:true});
 }catch{$('status').textContent='元ページを確認できません。ページで拡張を再実行してください。';}};
$('export').onclick=async()=>{try{const {records=[]}=await browser.storage.local.get('records');if(!records.length)throw Error('保存データがありません。');const blob=new Blob([records.map(x=>JSON.stringify(x)).join('\n')+'\n'],{type:'application/x-ndjson'});const url=URL.createObjectURL(blob);await browser.downloads.download({url,filename:'passbert-evaluation.jsonl',saveAs:true});setTimeout(()=>URL.revokeObjectURL(url),60000);}catch(e){$('status').textContent=e.message;}};
$('clear').onclick=async()=>{if(confirm('端末に保存した評価データをすべて削除しますか？')){await browser.storage.local.remove('records');await refresh();}};
await refresh();
