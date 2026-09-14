"""Independent, at most four native instances; smooth worst-deficit objective.

Outputs stay in revision3/agent_search. Do not run alongside eight main workers.
"""
from pathlib import Path
import argparse, json, time, multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from scipy.optimize import least_squares
from numpy.polynomial import Polynomial,Legendre
import optimize_revision3 as core

OUT=core.ROOT/'revision3'/'agent_search'

def initialize(seed,size,target,mode,higher):
    core.R=OUT
    core.initialize(seed,size,target,False,True)
    global MODE,HIGHER,NCOEF
    MODE=mode;HIGHER=higher;NCOEF=7 if higher else 5
    if higher:
        core.POWERS=np.arange(4,17,2)
        raw=np.array([core.sys.LDE.GetSurfaceAt(10).GetCellAt(i).DoubleValue*core.NORM**p
                      for i,p in zip(range(13,20),core.POWERS)])
        bb=Polynomial(raw).convert(kind=Legendre,domain=[0,1]).coef
        core.base_b=np.pad(bb,(0,max(0,7-len(bb))))
        def higher_apply(x):
            polynomial=Legendre(core.base_b+x[:7]*.03,domain=[0,1]).convert(kind=Polynomial).coef
            polynomial=np.pad(polynomial,(0,max(0,7-len(polynomial))))
            c=polynomial/core.NORM**core.POWERS
            for i,v in zip(range(13,20),c):core.sys.LDE.GetSurfaceAt(10).GetCellAt(i).DoubleValue=float(v)
            rr=core.base_r*(1+x[7:18]*.03)
            tt=core.base_t+x[18:29]*.35
            for i,v in zip(core.RIDS,rr):core.sys.LDE.GetSurfaceAt(i).Radius=float(v)
            for i,v in zip(core.TIDS,tt):core.sys.LDE.GetSurfaceAt(i).Thickness=float(v)
            core.sys.LDE.GetSurfaceAt(12).Thickness=float(core.base_focus)
            return c,rr,tt
        core.apply=higher_apply

def evaluate(xx,save=None):
    x=np.r_[xx,0.]
    _,record=core.evaluate(x,save)
    cc=np.array(record['asphere_A4_to_A12'])
    rr=np.linspace(0,15.8,401)
    sag=sum(c*rr**p for c,p in zip(cc,core.POWERS))
    slope=sum(c*p*rr**(p-1) for c,p in zip(cc,core.POWERS))
    record['asphere_powers']=core.POWERS.tolist()
    record['asphere_coefficients']=cc.tolist()
    record['asphere_A4_to_A12']=cc[:5].tolist()
    record['asphere_A14_to_A16']=cc[5:].tolist()
    record['asphere_max_abs_departure_mm']=float(np.max(abs(sag)))
    record['asphere_max_abs_extra_slope']=float(np.max(abs(slope)))
    v=np.array(record['results_flat'])
    d=core.refs+.009-v
    # Smooth clipping preserves the derivative as a trace crosses its lower bound.
    positive=.006*np.logaddexp(0,d/.006)
    if MODE=='smoothmax':
        # A differentiable largest-deficit aggregate, unlike active-index max.
        mx=float(np.max(d))
        smooth=mx+.012*np.log(np.mean(np.exp((d-mx)/.012)))
        optical=np.r_[positive**2/.065,8.*max(smooth,0.)]
    else:
        optical=positive**2/.03
    fo=np.array(record['first_order'])
    limits=np.array([.7,.3,1.,.3,.7,1.,.7,.3,.7])
    violation=np.maximum(limits-np.array(record['geometry_gaps']),0)
    residual=np.r_[optical,(fo-[148.1,135.9,36.6,77.416])*[1.5,1.,.55,.35],
                   max(0,abs(record['chief_full_field_height_mm']-193)-.3)*.05,
                   violation*8.,max(0,np.max(abs(sag))-.45)*3.,
                   max(0,np.max(abs(slope))-.12)*8.,xx*.0001]
    return residual.tolist(),record

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--seed',default=str(core.R/'focused_seed.zmx'))
    p.add_argument('--start',default=str(core.R/'broad_dense1_checkpoint.json'))
    p.add_argument('--target',default=str(core.R/'target_optimization.json'))
    p.add_argument('--name',default='smooth_central1')
    p.add_argument('--iterations',type=int,default=28)
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--size',type=int,default=256)
    p.add_argument('--step',type=float,default=.03)
    p.add_argument('--asphere-step',type=float,default=None)
    p.add_argument('--max-jacobians',type=int,default=0)
    p.add_argument('--mode',choices=['smoothmax','quartic'],default='smoothmax')
    p.add_argument('--higher-orders',action='store_true')
    p.add_argument('--asphere-only',action='store_true')
    a=p.parse_args()
    assert 1<=a.workers<=4
    OUT.mkdir(parents=True,exist_ok=True)
    start_record=json.loads(Path(a.start).read_text())
    rawx=np.array(start_record['x'])
    if a.higher_orders and len(rawx)==30:
        xx=rawx[:-1]
    else:
        xx=rawx[:27]
        if a.higher_orders:xx=np.r_[xx[:5],0.,0.,xx[5:]]
    ncoef=7 if a.higher_orders else 5
    dimensions=ncoef+22
    frozen=xx[ncoef:].copy()
    def expand(x):return np.r_[x,frozen] if a.asphere_only else x
    if a.asphere_only:
        xx=xx[:ncoef];dimensions=ncoef
    count=0;best=np.inf;bestx=xx.copy();begin=time.time();jacobians=0
    with ProcessPoolExecutor(max_workers=a.workers,mp_context=mp.get_context('spawn'),initializer=initialize,
                             initargs=(a.seed,a.size,a.target,a.mode,a.higher_orders)) as pool:
        def fun(x):
            nonlocal count,best,bestx
            if (OUT/(a.name+'.stop')).exists():raise StopIteration('Requested stop file')
            residual,rec=pool.submit(evaluate,expand(x)).result();count+=1
            fo=np.array(rec['first_order'])
            feasible=not rec['invalid_geometry'] and np.all(abs(fo-[148.1,135.9,36.6,77.416])<[.25,.4,.5,.6])
            score=rec['max_shortfall']+.2*rec['deficit_rms']
            summary=dict(rec,eval=count,score=score,seed=a.seed,target=a.target,sampling=a.size,
                         cost=float(np.dot(residual,residual)),seconds=time.time()-begin,mode=a.mode)
            (OUT/(a.name+'_current.json')).write_text(json.dumps(summary,indent=2))
            if feasible and score<best:
                best=score;bestx=x.copy()
                (OUT/(a.name+'_checkpoint.json')).write_text(json.dumps(summary,indent=2))
                pool.submit(evaluate,expand(x),str(OUT/(a.name+'_best.zmx'))).result()
            print(a.name,count,'max',round(rec['max_shortfall'],6),'best',round(best,6),
                  'first',np.round(fo,3),'secs',round(time.time()-begin),flush=True)
            return np.array(residual)
        def jac(x):
            nonlocal jacobians
            if a.max_jacobians and jacobians>=a.max_jacobians:raise StopIteration('Jacobian budget reached')
            jacobians+=1
            jobs=[]
            steps=[]
            for i in range(dimensions):
                h=a.asphere_step if a.asphere_step is not None and i<ncoef else a.step
                steps.append(h)
                plus=x.copy();minus=x.copy();plus[i]+=h;minus[i]-=h
                jobs.append((pool.submit(evaluate,expand(plus)),pool.submit(evaluate,expand(minus))))
            return np.array([(np.array(p.result()[0])-np.array(m.result()[0]))/(2*h) for (p,m),h in zip(jobs,steps)]).T
        low=np.r_[np.full(ncoef,-12.),np.full(11,-3.),np.full(11,-2.)]
        high=-low;low[ncoef+17]=-2.5;high[ncoef+17]=2.5
        if a.asphere_only:low=low[:ncoef];high=high[:ncoef]
        try:
            res=least_squares(fun,xx,jac=jac,bounds=(low,high),x_scale=1.,max_nfev=a.iterations,
                              ftol=2e-6,xtol=1e-7,gtol=1e-7)
            status=res.message
        except StopIteration as e:
            status=str(e)
        _,rec=pool.submit(evaluate,expand(bestx),str(OUT/(a.name+'_best.zmx'))).result()
        (OUT/(a.name+'_result.json')).write_text(json.dumps(dict(rec,status=status,score=best,
                                                                seed=a.seed,target=a.target,sampling=a.size,
                                                                seconds=time.time()-begin),indent=2))
        print('FINISHED',a.name,'maximum deficit',rec['max_shortfall'],flush=True)

if __name__=='__main__':main()
