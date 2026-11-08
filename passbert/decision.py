"""Optional explicit-attribute guards. Raw model output is always retained separately."""
def guard(form,prediction):
    fields=list(prediction['fields']);reasons=[None]*len(fields)
    for i,field in enumerate(form['fields']):
        hint=field['hint'];ac=field['autocomplete'].split()
        label=next((x for x in ac if x in ['username','email','current-password','new-password','one-time-code','search']),None)
        reason='autocomplete' if label else None
        if not label and field['type']=='password' and prediction['form'] in ['login','signup']:
            label='current-password' if prediction['form']=='login' else 'new-password';reason='password-type-and-purpose'
        if not label and field['type']!='password':
            if 'username' in hint or 'ユーザー' in hint:label='username';reason='identifier-hint'
            elif field['type']=='email':label='email';reason='email-type'
        if label and label!=fields[i]:fields[i]=label;reasons[i]=reason
    return {**prediction,'fields':fields,'guard_reasons':reasons,'raw_model':{'form':prediction['form'],'fields':prediction['fields']}}
