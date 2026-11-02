// Generated policy keeps Python and DOM extraction on the same vocabulary.
import { words, fieldLabels } from './policy.mjs';
const pattern = new RegExp([...words].sort((a,b)=>b.length-a.length).join('|'), 'giu');
const safe = text => [...String(text).slice(0,2048).matchAll(pattern)].map(x=>x[0].toLowerCase()).join(' ').slice(0,192);
export function extract(doc, { onField = () => {} } = {}) {
  const groups=[...doc.querySelectorAll('form')];
  return (groups.length?groups:[doc.body]).slice(0,32).flatMap(group=>{
    const fields=[...group.querySelectorAll('input,textarea,select')].slice(0,64).filter(el=>!['hidden','submit','button','checkbox','radio','file','image','reset'].includes((el.getAttribute('type')||'text').toLowerCase())&&!el.hasAttribute('hidden')&&el.getAttribute('aria-hidden')!=='true').map(el=>{
      onField(el);
      const label=(el.id?[...doc.querySelectorAll('label')].find(l=>l.htmlFor===el.id):null)||el.closest('label');
      const text=[];
      if(label){const walker=doc.createTreeWalker(label,4); let n; while((n=walker.nextNode())) if(!['TEXTAREA','SELECT','OPTION','INPUT','SCRIPT','STYLE','TEMPLATE','NOSCRIPT'].includes(n.parentElement.tagName)) text.push(n.textContent);}
      let type=(el.getAttribute('type')||'text').toLowerCase(); if(!['text','email','password','tel','number','search','url'].includes(type)) type='text';
      return {type,hint:safe([el.getAttribute('name')||'',el.id,el.getAttribute('placeholder')||'',el.getAttribute('aria-label')||'',text.join(' ')].join(' ')),autocomplete:(el.getAttribute('autocomplete')||'').split(/\s+/).filter(t=>fieldLabels.includes(t)).join(' ')};
    });
    const nodes=[...group.querySelectorAll('h1,h2,h3'),...group.querySelectorAll('button')];
    const text=nodes.map(n=>{const clone=n.cloneNode(true);clone.querySelectorAll('script,style,template,noscript,input,textarea,select,option').forEach(x=>x.remove());return clone.textContent;}).join(' ');
    return fields.length?[{context:safe(text),fields}]:[];
  });
}
export const serialize = form => '[CLS] '+form.context+' '+form.fields.map(f=>'[FLD] '+[f.type,f.hint,f.autocomplete].join(' ')).join(' ');
