"""CPU ONNX inference shared by automated audits and benchmarks."""
from pathlib import Path
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer
from passbert.data import FORMS,FIELDS
from passbert.windows import windows

class Classifier:
    def __init__(self, directory):
        root=Path(directory);self.tok=Tokenizer.from_file(str(root/'tokenizer.json'))
        options=ort.SessionOptions();options.intra_op_num_threads=2
        self.session=ort.InferenceSession(str(root/'model.int8.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
    def predict(self,form):
        chunks=windows(self.tok,form);form_logits=[];fields=[None]*len(form['fields'])
        for ids,positions,indices in chunks:
            inputs=np.asarray([ids],dtype=np.int64)
            logits=self.session.run(None,{'input_ids':inputs,'attention_mask':np.ones_like(inputs)})[0][0]
            form_logits.append(logits[0,:len(FORMS)])
            for p,index in zip(positions,indices):fields[index]=FIELDS[int(logits[p,len(FORMS):].argmax())]
        return {'form':FORMS[int(np.mean(form_logits,axis=0).argmax())], 'fields':fields,'windows':len(chunks)}
