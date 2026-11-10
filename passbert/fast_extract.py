"""Native HTML5 extraction for archive throughput; same feature contract as data.extract."""
import re
from selectolax.lexbor import LexborHTMLParser
from passbert.data import FIELDS,safe
from passbert.annotation import sanitize as annotation_safe,AUTOCOMPLETE


def extract_fast(html, *, annotation_builder=None):
 tree=LexborHTMLParser(html[:1_000_000])
 for node in tree.css('script,style,template,noscript'):node.decompose()
 def attrs(node):return node.attributes or {}
 by_id={};labels={};form_ids={}
 for node in tree.css('[id]'):by_id.setdefault(attrs(node)['id'],node)
 for node in tree.css('label[for]'):labels.setdefault(attrs(node)['for'],node)
 groups=[];group_index={}
 for node in tree.css('form'):
    pair=(node,[]);groups.append(pair);group_index[node.mem_id]=pair
    if 'id' in attrs(node):form_ids.setdefault(attrs(node)['id'],node)
 visible_cache={};group_cache={};blocked_cache={}
 blocked={'script','style','template','noscript','input','textarea','select','option'}
 def visible(node):
    if node is None:return True
    key=node.mem_id
    if key in visible_cache:return visible_cache[key]
    a=attrs(node);style=re.sub(r'\s+','',(a.get('style') or '').lower())
    result='hidden' not in a and (a.get('aria-hidden') or '').lower()!='true' and not re.search(r'(?:^|;)(?:display:none|visibility:hidden)(?:;|$|!)',style)
    result=bool(result and visible(node.parent));visible_cache[key]=result;return result
 def blocked_text(node):
    if node is None:return False
    key=node.mem_id
    if key in blocked_cache:return blocked_cache[key]
    a=attrs(node);value=(a.get('contenteditable') if 'contenteditable' in a else 'false') or ''
    result=node.tag in blocked or value.lower()!='false' or blocked_text(node.parent)
    blocked_cache[key]=result;return result
 def text(node):
    if node is None:return ''
    return ' '.join(t.text_content for t in node.traverse(include_text=True) if t.is_text_node and not blocked_text(t.parent))
 def owner(el):
    a=attrs(el)
    if 'form' in a:root=form_ids.get(a['form'])
    else:
        root=el.parent
        while root is not None and root.tag!='form':root=root.parent
    if root is not None:return root
    parent=el.parent
    while parent is not None and parent.tag not in ['body','html','-document']:
        key=parent.mem_id
        if key not in group_cache:
            has_form=any(n.mem_id!=key for n in parent.css('form'))
            has_button=any(n.mem_id!=key for n in parent.css('button,input[type=submit]'))
            group_cache[key]=not has_form and has_button
        if group_cache[key]:return parent
        parent=parent.parent
    return tree.body
 for el in tree.css('input,textarea,select'):
    a=attrs(el)
    if (a.get('type') or 'text').lower() in ['hidden','submit','button','checkbox','radio','file','image','reset'] or not visible(el):continue
    root=owner(el)
    if root is None:continue
    pair=group_index.get(root.mem_id)
    if pair is None:pair=(root,[]);groups.append(pair);group_index[root.mem_id]=pair
    if len(pair[1])<64:pair[1].append(el)
 output=[];views=[]
 for root,elements in groups:
    if not elements:continue
    fields=[];annotation_fields=[]
    for el in elements:
        a=attrs(el);label=labels.get(a.get('id')) if a.get('id') else None
        if label is None:
            parent=el.parent
            while parent is not None and parent.tag!='label':parent=parent.parent
            label=parent
        refs=[by_id.get(value) for value in (a.get('aria-labelledby') or '').split()[:8]]
        kind=(a.get('type') or 'text').lower()
        if kind not in ['text','email','password','tel','number','search','url']:kind='text'
        hint=' '.join([a.get('name') or '',a.get('id') or '',a.get('placeholder') or '',a.get('aria-label') or '',text(label),*(text(n) for n in refs)])
        ac=(a.get('autocomplete') or '').lower().split()
        fields.append({'type':kind,'hint':safe(hint),'autocomplete':' '.join(t for t in ac if t in FIELDS)})
        annotation_fields.append({'type':kind,'hint':annotation_safe(hint),'autocomplete':' '.join(t for t in ac if t in AUTOCOMPLETE)})
    headings=root.css('h1,h2,h3')
    if not headings:
        cursor=root
        for _ in range(3):
            sib=cursor.prev
            while sib is not None:
                if not sib.tag.startswith('-'):
                    if sib.tag=='form' or sib.css_first('form') is not None:break
                    candidates=[sib] if sib.tag in ['h1','h2','h3'] else sib.css('h1,h2,h3')
                    if candidates:headings=[candidates[-1]];break
                sib=sib.prev
            if headings or cursor.parent is None or cursor.parent.tag in ['body','html','-document']:break
            cursor=cursor.parent
    context=' '.join(text(n) for n in headings+root.css('button'))
    output.append({'context':safe(context),'fields':fields})
    if annotation_builder is None:views.append({'context':annotation_safe(context),'fields':annotation_fields})
    else:
        def visible_text(node):
            if node is None:return ''
            return ' '.join(t.text_content for t in node.traverse(include_text=True) if t.is_text_node and not blocked_text(t.parent) and visible(t.parent))
        views.append(annotation_builder(root,elements,headings,{'text':visible_text,'visible':visible,'by_id':by_id,'labels':labels}))
    if len(output)>=32:break
 return output,views
