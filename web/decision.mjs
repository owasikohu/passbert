// Optional rules are reported separately from the raw model, including every override reason.
export function guard(form,prediction){
 const fields=[...prediction.fields],reasons=fields.map(()=>null);
 form.fields.forEach((field,i)=>{
  let label=field.autocomplete.split(/\s+/).find(x=>['username','email','current-password','new-password','one-time-code','search'].includes(x));
  let reason=label?'autocomplete':null;
  if(!label&&field.type==='password'&&['login','signup'].includes(prediction.form)){label=prediction.form==='login'?'current-password':'new-password';reason='password-type-and-purpose';}
  if(!label&&field.type!=='password'){
   if(field.hint.includes('username')||field.hint.includes('ユーザー')){label='username';reason='identifier-hint';}
   else if(field.type==='email'){label='email';reason='email-type';}
  }
  if(label&&label!==fields[i]){fields[i]=label;reasons[i]=reason;}
 });
 return {...prediction,fields,guard_reasons:reasons,raw_model:{form:prediction.form,fields:prediction.fields}};
}
