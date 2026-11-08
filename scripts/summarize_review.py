"""Compare blind model opinions without calling either model ground truth."""
import argparse
import json
from collections import Counter,defaultdict
from pathlib import Path
from passbert.review import parse_labels


def summarize(requests,proposals,reviews,controls):
    request_map={r['record_id']:r for r in requests};proposal_map={r['record_id']:r for r in proposals};control_map={r['record_id']:r for r in controls}
    if len(request_map)!=len(requests):raise ValueError('Duplicate request identity')
    result_map={}
    for r in reviews:
        if r['record_id'] not in request_map:raise ValueError('Unknown review identity')
        if r['record_id'] in result_map:raise ValueError('Duplicate review identity')
        result_map[r['record_id']]=r
    counts=Counter();by_route=defaultdict(Counter);by_language=defaultdict(Counter);form_confusions=Counter();field_confusions=Counter();cases=[];control_results=[]
    for record_id,request in request_map.items():
        response=result_map.get(record_id);counts['requests']+=1
        valid=False
        if response and response.get('status')=='valid':
            try:parsed=parse_labels(json.dumps({k:response[k] for k in ['form_label','field_labels']}),len(request['form']['fields']));valid=True
            except (ValueError,KeyError):pass
        if request['kind']=='control':
            expected=control_map[record_id];exact=valid and parsed['form_label']==expected['form_label'] and parsed['field_labels']==expected['field_labels']
            control_results.append({'record_id':record_id,'valid':valid,'exact':exact,'expected':expected,'review':parsed if valid else None});continue
        counts['corpus_requests']+=1;proposal=proposal_map[record_id];original=proposal['prediction'];route=proposal['decision']['status'];language=request['language']
        cohort=by_route[route];lang=by_language[language];cohort['requests']+=1;lang['requests']+=1
        if not valid:
            status='missing_or_invalid';counts[status]+=1;cohort[status]+=1;lang[status]+=1
            cases.append({'record_id':record_id,'status':status});continue
        counts['valid_reviews']+=1
        unknown=parsed['form_label']=='unreviewable';field_unknown=sum(x=='unreviewable' for x in parsed['field_labels'])
        counts['unreviewable_forms']+=unknown;counts['unreviewable_fields']+=field_unknown;counts['fields']+=len(parsed['field_labels'])
        if not unknown:
            counts['form_comparisons']+=1;counts['form_agreements']+=parsed['form_label']==original['form'];form_confusions[(original['form'],parsed['form_label'])]+=1
        corroborated=[]
        for i,(left,right) in enumerate(zip(original['fields'],parsed['field_labels'])):
            if right!='unreviewable':
                counts['field_comparisons']+=1;counts['field_agreements']+=left==right;field_confusions[(left,right)]+=1
            corroborated.append(bool(right!='unreviewable' and left==right and proposal['decision']['field_agreement_candidates'][i]))
        counts['corroborated_weak_field_candidates']+=sum(corroborated)
        if unknown or field_unknown:status='abstained_or_partial'
        elif parsed['form_label']==original['form'] and parsed['field_labels']==original['fields']:status='cross_model_agreement_candidate'
        else:status='cross_model_disagreement'
        counts[status]+=1;cohort[status]+=1;lang[status]+=1
        cases.append({'record_id':record_id,'original_route':route,'language':language,'status':status,'zap':original,'review':parsed,'corroborated_weak_field_candidates':corroborated,'verified':False,'training_eligible':False})
    return {'scope':'Stratified train-only blind model review, not model accuracy or gold annotation','counts':dict(counts),'by_original_route':{k:dict(v) for k,v in by_route.items()},'by_language':{k:dict(v) for k,v in by_language.items()},'controls':{'total':len(control_results),'valid':sum(x['valid'] for x in control_results),'exact':sum(x['exact'] for x in control_results),'results':control_results},'form_comparisons':[{'zap':a,'reviewer':b,'count':n} for (a,b),n in form_confusions.most_common()],'field_comparisons':[{'zap':a,'reviewer':b,'count':n} for (a,b),n in field_confusions.most_common()],'cases':cases,'gold_labels':0,'training_promotions':0,'limitations':['Qwen-family reviewer and original Zap teacher may share correlated biases','Descriptor information loss can make the correct label unknowable','Agreement is not correctness, disagreement does not identify which model is wrong','Twenty examples per original route are not representative prevalence estimates']}


def main():
 p=argparse.ArgumentParser();p.add_argument('--root',default='artifacts/blind-review');p.add_argument('--reviews',default='artifacts/blind-review/output/review-output/reviews.jsonl');args=p.parse_args();root=Path(args.root)
 def lines(path):return [json.loads(l) for l in Path(path).read_text().splitlines() if l]
 report=summarize(lines(root/'blind-local.jsonl'),lines('artifacts/corpus-10k/label-pilot/proposals.jsonl'),lines(args.reviews),json.loads((root/'controls-local.json').read_text()))
 (root/'assessment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['cases','form_comparisons','field_comparisons']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
