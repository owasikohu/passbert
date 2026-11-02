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
  return {encode,async predict(form){
    const ids=encode(serialize(form));if(ids.length>256)throw Error('Form exceeds 256 tokens');
    const start=performance.now();
    const result=await session.run({input_ids:new ort.Tensor('int64',BigInt64Array.from(ids,BigInt),[1,ids.length]),attention_mask:new ort.Tensor('int64',BigInt64Array.from(ids,()=>1n),[1,ids.length])});
    const logits=result.logits.data;const count=formLabels.length+fieldLabels.length;
    const argmax=(pos,offset,size)=>{let best=0;for(let j=1;j<size;j++)if(logits[pos*count+offset+j]>logits[pos*count+offset+best])best=j;return best;};
    return {form:formLabels[argmax(0,0,formLabels.length)],fields:ids.flatMap((id,i)=>id===vocab['[FLD]']?[fieldLabels[argmax(i,formLabels.length,fieldLabels.length)]]:[]),model_ms:performance.now()-start};
  }};
}
