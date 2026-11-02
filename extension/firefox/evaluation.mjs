import {formLabels,fieldLabels} from '../../web/policy.mjs';
export const UNREVIEWABLE='unreviewable';
export function metrics(records) {
  const counts={form:{correct:0,total:0},field:{correct:0,total:0}};
  for(const record of records) for(const row of record.rows){
    if(row.form_label!==UNREVIEWABLE && row.prediction){counts.form.total++;counts.form.correct+=Number(row.form_label===row.prediction.form);}
    row.field_labels.forEach((label,i)=>{if(label!==UNREVIEWABLE && row.prediction){counts.field.total++;counts.field.correct+=Number(label===row.prediction.fields[i]);}});
  }
  return counts;
}
export function makeRecord(snapshot,annotations,predictions,language,model) {
  if(!['ja','en','mixed','other'].includes(language))throw Error('Invalid language');
  if(annotations.length!==snapshot.forms.length||predictions.length!==snapshot.forms.length)throw Error('Form alignment mismatch');
  return {schema_version:1,evaluation_only:true,annotation_protocol:'labels-before-prediction; locked-after-reveal',source:'firefox-manual-v1',snapshot_id:snapshot.id,site_id:snapshot.site_id,site_grouping:'sha256-hostname-not-registrable-domain',captured_at:snapshot.captured_at,language,model,scope:'top-frame; light DOM; first 32 groups / 64 controls per group',extraction_ms:snapshot.extraction_ms,rows:snapshot.forms.map((form,i)=>{
    const a=annotations[i];if(![...formLabels,UNREVIEWABLE].includes(a.form_label)||a.field_labels.some(x=>![...fieldLabels,UNREVIEWABLE].includes(x))||a.field_labels.length!==form.fields.length||a.field_labels.some(x=>!x))throw Error('すべての正解ラベルを選択してください。');
    if(predictions[i]&&predictions[i].fields.length!==form.fields.length)throw Error('Prediction alignment mismatch');
    return {form,form_label:a.form_label,field_labels:a.field_labels,prediction:predictions[i],visibility:snapshot.visibility[i]};
  })};
}
