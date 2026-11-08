import { serialize } from './extract.mjs';
import { fieldLabels, formLabels } from './policy.mjs';
// Pass a locally bundled onnxruntime-web namespace. Use the WASM CPU backend.
export async function load(ort, base) {
  const tokenizer=await (await fetch(base+'/tokenizer.json')).json();
  const vocab=tokenizer.model.vocab;
  const encode=text=>{
    const ids=[];
    for(const part of text.split(/(\[CLS\]|\[FLD\])/u).filter(Boolean)) {
      if(part==='[CLS]'||part==='[FLD]'){ids.push(vocab[part]);continue;}
      const tokens=part.match(/[\p{P}\x21-\x2f\x3a-\x40\x5b-\x60\x7b-\x7e]|[^\s\p{P}\x21-\x2f\x3a-\x40\x5b-\x60\x7b-\x7e]+/gu)||[];
      for(const word of tokens){
        const chars=[...word];let start=0;const pieces=[];
        if(chars.length>100){ids.push(vocab['[UNK]']);continue;}
        while(start<chars.length){let end=chars.length,id;
          for(;end>start;end--){id=vocab[(start?'##':'')+chars.slice(start,end).join('')];if(id!==undefined)break;}
          if(end===start){pieces.length=0;pieces.push(vocab['[UNK]']);break;}
          pieces.push(id);start=end;
        }ids.push(...pieces);
      }
    }return ids;
  };
  const session=await ort.InferenceSession.create(base+'/model.int8.onnx',{executionProviders:['wasm']});
  function windows(form){
    const context=[vocab['[CLS]'],...encode(form.context).slice(0,64)];
    const chunks=[];let ids=[...context],positions=[],indices=[];
    form.fields.forEach((field,index)=>{
      const tokens=encode('[FLD] '+[field.type,field.hint,field.autocomplete].join(' '));
      if(tokens.length>256-context.length)throw Error('One field exceeds the whole-field token budget');
      if(ids.length+tokens.length>256){chunks.push({ids,positions,indices});ids=[...context];positions=[];indices=[];}
      positions.push(ids.length);indices.push(index);ids.push(...tokens);
    });
    if(indices.length)chunks.push({ids,positions,indices});
    if(!chunks.length)throw Error('Cannot classify a form without fields');
    return chunks;
  }
  return {encode,windows,async predict(form){
    const chunks=windows(form);const start=performance.now();
    const totals=new Float64Array(formLabels.length);const fields=new Array(form.fields.length);
    const count=formLabels.length+fieldLabels.length;
    const argmax=arr=>{let best=0;for(let j=1;j<arr.length;j++)if(arr[j]>arr[best])best=j;return best;};
    for(const {ids,positions,indices} of chunks){
      const result=await session.run({input_ids:new ort.Tensor('int64',BigInt64Array.from(ids,BigInt),[1,ids.length]),attention_mask:new ort.Tensor('int64',BigInt64Array.from(ids,()=>1n),[1,ids.length])});
      const logits=result.logits.data;
      for(let j=0;j<formLabels.length;j++)totals[j]+=logits[j];
      positions.forEach((p,j)=>{fields[indices[j]]=fieldLabels[argmax(logits.slice(p*count+formLabels.length,(p+1)*count))];});
    }
    return {form:formLabels[argmax(totals)],fields,windows:chunks.length,model_ms:performance.now()-start};
  }};
}
