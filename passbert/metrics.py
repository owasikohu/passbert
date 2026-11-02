"""Dependency-free classification metrics shared by training and evaluation."""
def score(truth, pred, classes):
    result = {}; f1s=[]
    for c in classes:
        tp=sum(a==c and b==c for a,b in zip(truth,pred)); fp=sum(a!=c and b==c for a,b in zip(truth,pred)); fn=sum(a==c and b!=c for a,b in zip(truth,pred))
        f1=2*tp/max(1,2*tp+fp+fn); f1s.append(f1)
        result[c]={'f1':f1,'support':truth.count(c)}
    return {'accuracy':sum(a==b for a,b in zip(truth,pred))/max(1,len(truth)), 'macro_f1':sum(f1s)/len(f1s),'per_class':result}

