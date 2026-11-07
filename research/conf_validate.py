import sys, numpy as np, pandas as pd
sys.path.insert(0,'src'); sys.path.insert(0,'prereg')
import lib, lib3, screens
from scipy.stats import rankdata
rng=np.random.default_rng(20261106)
def auc(y,s):
    y=np.asarray(y,bool); s=np.asarray(s,float)
    n1,n0=y.sum(),(~y).sum()
    if n1==0 or n0==0: return np.nan
    r=rankdata(s); return (r[y].sum()-n1*(n1+1)/2)/(n1*n0)
def auc_ci(y,s,cl,B=1000):
    y=np.asarray(y,bool); s=np.asarray(s,float); cl=np.asarray(cl); u=np.unique(cl); groups=[np.where(cl==k)[0] for k in u]; out=[]
    for _ in range(B):
        idx=np.concatenate([groups[i] for i in rng.integers(0,len(u),len(u))]); a=auc(y[idx],s[idx]); 
        if not np.isnan(a): out.append(a)
    return np.percentile(out,[2.5,97.5])
def wilson(k,n,z=1.96):
    if n==0: return (np.nan,np.nan)
    p=k/n; d=1+z*z/n; c=p+z*z/(2*n); h=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n)); return ((c-h)/d,(c+h)/d)
def episodes_for(d0,d1):
    df=lib3.prep2(lib3.load2('out2/elig_feat_*.parquet',d0,d1)); df['d']=pd.to_datetime(df.d); df=df.reset_index(drop=True)
    sc=screens.screens(df); S={k:pd.Series(np.asarray(v),index=df.index) for k,v in sc.items()}
    S['R2a']=df.eval('d200>=0.53 & rs<=0.8 & sq<=5.3'); S['R2b']=df.eval('d200>=0.37 & ldvk<=0.3 & lpk<=0.5')
    sig=['A3','A2','B3','R2a','R2b']; df['n']=sum(S[k].astype(int) for k in sig)
    idx=lib.episodes(df,df.n>0,20); e=df.loc[idx].copy()
    e['liq']=np.where(e.dv50p>=2e7,1.0,np.where(e.dv50p>=5e6,0.75,0.5)); e['px']=np.where(e.ct>=5,1.0,0.6); e['setup']=np.minimum(100,25*e.n)
    e['exec']=100*(e.liq+e.px+1.0)/3; e['E50']=e.e50>0.5; e['pos']=e.xnet>0
    return e
res={}
for nm,(d0,d1) in {'D2':('2019-01-01','2021-09-30'),'V2':('2022-01-01','2023-09-30')}.items():
    e=episodes_for(d0,d1); res[nm]=e; print(nm,'episodes',len(e),'E50 rate',round(e.E50.mean(),4),'xnet>0',round(e.pos.mean(),3),'months',e.ym.nunique(),flush=True)
rows=[]
for nm,e in res.items():
    for name,s in (('V1/V2 setup n',e.n),('V3 execution',e['exec'])):
        for tgt in ('E50','pos'):
            a=auc(e[tgt],s); lo,hi=auc_ci(e[tgt],s,e.ym); rows.append((nm,name,tgt,len(e),round(a,4),round(lo,4),round(hi,4)))
out=pd.DataFrame(rows,columns=['seg','score','target','n','AUC','lo95','hi95']); pd.set_option('display.width',200); print(out.to_string(index=False))
ship=all(out[(out.score=='V1/V2 setup n')&(out.target=='E50')].lo95>0.5); print('SETUP SHIPS:',ship)
# V5 hit rates by n bucket
e=pd.concat([res['D2'].assign(seg='D2'),res['V2'].assign(seg='V2')]); e['nb']=np.minimum(e.n,3)
r5=[]
for seg,g0 in list(e.groupby('seg'))+[('POOLED',e)]:
    for b,g in g0.groupby('nb'):
        k=int(g.E50.sum()); n=len(g); lo,hi=wilson(k,n); r5.append((seg,b,n,round(k/n,4),round(lo,4),round(hi,4),round(g.xnet.mean(),4)))
v5=pd.DataFrame(r5,columns=['seg','n_bucket','episodes','P_E50','lo','hi','mean_xnet']); print(v5.to_string(index=False)); v5.to_csv('cat/conf_v5.csv',index=False)
# V4 final score (both variants), on V2
for variant,w in (('with setup (35%)',0.35),('execution only',0.0)):
    for nm in ('D2','V2'):
        g=res[nm]; sc=w*g.setup+(1-w)*g['exec']
        for tgt in ('E50','pos'):
            a=auc(g[tgt],sc); lo,hi=auc_ci(g[tgt],sc,g.ym); print('V4',variant,nm,tgt,round(a,4),(round(lo,4),round(hi,4)))
out.to_csv('cat/conf_auc.csv',index=False)
# V6 merger/tender flag on V2
cf=pd.read_parquet('cat/cat_features.parquet'); cf['d']=pd.to_datetime(cf.d)
g=res['V2'].merge(cf[['symbol','d','fmerger_90','foffer_90','f8k_302_30']],on=['symbol','d'],how='left')
for col in ['fmerger_90','foffer_90','f8k_302_30']:
    a=g[g[col]>0]; b=g[~(g[col]>0)]
    print('V6',col,'flagged n',len(a),'E50',round(a.E50.mean(),4) if len(a) else None,'xnet',round(a.xnet.mean(),4) if len(a) else None,'| others n',len(b),'E50',round(b.E50.mean(),4),'xnet',round(b.xnet.mean(),4))
