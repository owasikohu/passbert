"""Dependency-light routing of weak label proposals; does not verify correctness."""
from passbert.data import FORMS,FIELDS

def route(form,prediction,heuristic,no_ac):
    purpose,fields=heuristic
    unknown=prediction['form'] not in FORMS or any(label not in FIELDS for label in prediction['fields'])
    complete_agreement=prediction['form']==purpose and prediction['fields']==fields
    confident=prediction['form_confidence']>=.95 and min(prediction['field_confidences'],default=0)>=.95
    stable=prediction['form']==no_ac['form'] and prediction['fields']==no_ac['fields']
    if unknown:status='taxonomy_review'
    elif not complete_agreement:status='disagreement_review'
    elif not confident:status='low_confidence_review'
    elif not stable:status='autocomplete_dependence_review'
    else:status='agreement_candidate'
    field_candidates=[label in FIELDS and confidence>=.95 and label==rule and label==ablated for label,confidence,rule,ablated in zip(prediction['fields'],prediction['field_confidences'],fields,no_ac['fields'])]
    return {'field_agreement_candidates':field_candidates,'status':status,'verified':False,'training_eligible':False,'teacher_heuristic_agree':complete_agreement,'confident':confident,'autocomplete_ablation_stable':stable,'proposed_form_label':prediction['form'] if prediction['form'] in FORMS else None,'proposed_field_labels':[label if label in FIELDS else None for label in prediction['fields']]}
