"""Whole-field windows: every field is classified exactly once, with repeated context."""
def windows(tok,form,max_length=256):
    context=[tok.token_to_id('[CLS]')]+tok.encode(form['context']).ids[:64]
    budget=max_length-len(context);result=[];ids=list(context);positions=[];indices=[]
    for index,field in enumerate(form['fields']):
        tokens=tok.encode('[FLD] '+' '.join(field[k] for k in ['type','hint','autocomplete'])).ids
        if len(tokens)>budget:raise ValueError('One field exceeds the whole-field token budget')
        if len(ids)+len(tokens)>max_length:
            result.append((ids,positions,indices));ids=list(context);positions=[];indices=[]
        positions.append(len(ids));indices.append(index);ids.extend(tokens)
    if indices:result.append((ids,positions,indices))
    if not result:raise ValueError('Cannot classify a form without fields')
    return result
