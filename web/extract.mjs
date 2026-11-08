import { words, fieldLabels } from './policy.mjs';
const pattern = new RegExp([...words].sort((a,b)=>b.length-a.length).join('|'), 'giu');
const safe = text => [...String(text).slice(0,2048).matchAll(pattern)].map(x=>x[0].toLowerCase()).join(' ').slice(0,192);
export function extract(doc, { onField = () => {} } = {}) {
  if(!doc.body)return [];
  const blocked='script,style,template,noscript,input,textarea,select,option,[contenteditable]:not([contenteditable="false"])';
  function text(node){
    if(!node)return '';const parts=[];const walker=doc.createTreeWalker(node,4);let n;
    while((n=walker.nextNode()))if(!n.parentElement.closest(blocked))parts.push(n.textContent);
    return parts.join(' ');
  }
  function eligible(el){
    if(el.closest('script,style,template,noscript'))return false;
    if(['hidden','submit','button','checkbox','radio','file','image','reset'].includes((el.getAttribute('type')||'text').toLowerCase()))return false;
    for(let n=el;n;n=n.parentElement){
      if(n.hasAttribute('hidden')||(n.getAttribute('aria-hidden')||'').toLowerCase()==='true')return false;
      const style=(n.getAttribute('style')||'').toLowerCase().replace(/\s+/g,'');
      if(/(?:^|;)(?:display:none|visibility:hidden)(?:;|$|!)/.test(style))return false;
    }return true;
  }
  const groups=[...doc.querySelectorAll('form')].map(root=>({root,elements:[]}));
  for(const el of doc.querySelectorAll('input,textarea,select')){
    if(!eligible(el))continue;
    let owner=el.hasAttribute('form')?doc.getElementById(el.getAttribute('form')):el.closest('form');
    if(owner?.tagName!=='FORM')owner=null;
    if(!owner){
      for(let parent=el.parentElement;parent&&!['BODY','HTML'].includes(parent.tagName);parent=parent.parentElement){
        if(!parent.querySelector('form')&&parent.querySelector('button,input[type="submit"]')){owner=parent;break;}
      }
    }
    owner??=doc.body;
    let group=groups.find(g=>g.root===owner);if(!group){group={root:owner,elements:[]};groups.push(group);}
    if(group.elements.length<64)group.elements.push(el);
  }
  const output=[];
  for(const {root,elements} of groups){
    if(!elements.length)continue;
    const fields=elements.map(el=>{
      onField(el);
      const label=(el.id?[...doc.querySelectorAll('label')].find(l=>l.htmlFor===el.id):null)||el.closest('label');
      const refs=(el.getAttribute('aria-labelledby')||'').split(/\s+/).filter(Boolean).slice(0,8).map(id=>doc.getElementById(id));
      let type=(el.getAttribute('type')||'text').toLowerCase();if(!['text','email','password','tel','number','search','url'].includes(type))type='text';
      return {type,hint:safe([el.getAttribute('name')||'',el.id,el.getAttribute('placeholder')||'',el.getAttribute('aria-label')||'',text(label),...refs.map(text)].join(' ')),autocomplete:(el.getAttribute('autocomplete')||'').toLowerCase().split(/\s+/).filter(t=>fieldLabels.includes(t)).join(' ')};
    });
    let headings=[...root.querySelectorAll('h1,h2,h3')];let cursor=root;
    for(let level=0;!headings.length&&level<3;level++){
      for(let sib=cursor.previousElementSibling;sib;sib=sib.previousElementSibling){
        if(sib.tagName==='FORM'||sib.querySelector('form'))break;
        const candidates=sib.matches('h1,h2,h3')?[sib]:[...sib.querySelectorAll('h1,h2,h3')];
        if(candidates.length){headings=[candidates.at(-1)];break;}
      }
      if(headings.length||!cursor.parentElement||['BODY','HTML'].includes(cursor.parentElement.tagName))break;
      cursor=cursor.parentElement;
    }
    output.push({context:safe([...headings,...root.querySelectorAll('button')].map(text).join(' ')),fields});
    if(output.length>=32)break;
  }return output;
}
export const serialize = form => '[CLS] '+form.context+' '+form.fields.map(f=>'[FLD] '+[f.type,f.hint,f.autocomplete].join(' ')).join(' ');
