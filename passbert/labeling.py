"""Local Zap teacher proposals. Agreement is weak supervision, never verified ground truth."""
import torch
from transformers import AutoTokenizer,AutoModelForTokenClassification
from passbert.data import FORMS,FIELDS

ZAP_REVISION='0ab38d45793577230569ad77e0e52fcdfb67b9dc'
class ZapTeacher:
    def __init__(self,path):
        torch.set_num_threads(2)
        self.tok=AutoTokenizer.from_pretrained(path,local_files_only=True,trust_remote_code=False)
        self.model=AutoModelForTokenClassification.from_pretrained(path,local_files_only=True,trust_remote_code=False).float().eval()
        labels=self.model.config.id2label
        self.form_ids=[i for i in sorted(labels) if labels[i].startswith('form:')]
        self.field_ids=[i for i in sorted(labels) if labels[i].startswith('field:')]
        self.form_names=[labels[i][5:] for i in self.form_ids];self.field_names=[labels[i][6:] for i in self.field_ids]
    @torch.no_grad()
    def predict(self,form,without_autocomplete=False):
        context=self.tok('[HEAD] '+form['context'],add_special_tokens=False)['input_ids'][:160]
        prefix=[self.tok.cls_token_id]+context;chunks=[];ids=list(prefix);positions=[];indices=[]
        for index,field in enumerate(form['fields']):
            text='[FLD] [TYPE] '+field['type']
            if field['autocomplete'] and not without_autocomplete:text+=' [AC] '+field['autocomplete']
            if field['hint']:text+=' [LBL] '+field['hint']
            tokens=self.tok(text,add_special_tokens=False)['input_ids'][:120]
            if len(ids)+len(tokens)+1>512:
                chunks.append((ids+[self.tok.sep_token_id],positions,indices));ids=list(prefix);positions=[];indices=[]
            positions.append(len(ids));indices.append(index);ids.extend(tokens)
        if indices:chunks.append((ids+[self.tok.sep_token_id],positions,indices))
        if not chunks:raise ValueError('No fields')
        form_logits=[];labels=[None]*len(form['fields']);confidences=[0.0]*len(labels)
        for ids,positions,indices in chunks:
            x=torch.tensor([ids]);logits=self.model(input_ids=x,attention_mask=torch.ones_like(x)).logits[0].float()
            form_logits.append(logits[0,self.form_ids])
            for pos,index in zip(positions,indices):
                probabilities=torch.softmax(logits[pos,self.field_ids],dim=-1);top=int(probabilities.argmax())
                labels[index]=self.field_names[top];confidences[index]=float(probabilities[top])
        probabilities=torch.softmax(torch.stack(form_logits).mean(0),dim=-1);top=int(probabilities.argmax())
        return {'form':self.form_names[top],'fields':labels,'form_confidence':float(probabilities[top]),'field_confidences':confidences}

from passbert.label_policy import route
