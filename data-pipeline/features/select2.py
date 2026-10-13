import math, sys, numpy as np
sys.argv=['x']; import feature_model as FM
from sklearn.ensemble import HistGradientBoostingRegressor
rows=FM.load_rows(); X=FM.SP.sample([r['lat'] for r in rows],[r['lng'] for r in rows]); y=np.array([r['y'] for r in rows]); w0=np.array([r['w'] for r in rows])
t=np.array([r['loc_level']=='titik' for r in rows]); fo=np.array([r['fold'] for r in rows])
def hgb(**k):
    base=dict(max_iter=250,learning_rate=0.06,max_leaf_nodes=15,min_samples_leaf=30,l2_regularization=1.0,monotonic_cst=[FM.MONO.get(f,0) for f in FM.FEATS],random_state=0); base.update(k)
    return lambda X,y,w: HistGradientBoostingRegressor(**base).fit(X,y,sample_weight=w)
def ridge(X,y,w): return FM.fit('ridge',X,y,w)
def cvp(fn,w):
    p=np.zeros(len(y))
    for k in range(5):
        tr=fo!=k; p[~tr]=fn(X[tr],y[tr],w[tr]).predict(X[~tr])
    return p
def rep(n,p):
    a=np.abs(p-y)[t]; print(f'{n:28s} {(math.exp(np.median(a))-1)*100:5.1f}% bias {np.median((p-y)[t]):+.3f}',flush=True); return p
P={}
P['ridge']=rep('ridge',cvp(ridge,w0))
P['hgb']=rep('hgb',cvp(hgb(),w0))
P['hgb_reg']=rep('hgb leaf60 nodes8',cvp(hgb(min_samples_leaf=60,max_leaf_nodes=8,max_iter=300),w0))
P['hgb_slow']=rep('hgb lr.03 it500 leaf40',cvp(hgb(learning_rate=0.03,max_iter=500,min_samples_leaf=40),w0))
w1=np.where(t,1.0,0.2); P['ridge_w']=rep('ridge kel-w .2',cvp(ridge,w1)); P['hgb_w']=rep('hgb kel-w .2',cvp(hgb(min_samples_leaf=60,max_leaf_nodes=8,max_iter=300),w1))
rep('avg ridge+hgb_reg',(P['ridge']+P['hgb_reg'])/2)
rep('avg ridge_w+hgb_w',(P['ridge_w']+P['hgb_w'])/2)
