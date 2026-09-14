"""Independent R4 search, four apps maximum, every asphere highest A6.

R3 high-order departure is only a fitting reference for physically sane starts.
Every traced/saved candidate explicitly has A2=A8...A16=Conic=0.
"""
from pathlib import Path
import argparse,json,time,multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from numpy.polynomial import Polynomial,Legendre
from scipy.optimize import least_squares
import optimize_revision3 as core

OUT=core.ROOT/'revision4'/'root_search'
NORM=15.5
MODES=['area_sag','uniform_sag','sag_slope','edge_sag']

def fit_departure(coefficients):
    r=np.linspace(.03,15.5,801);u=(r/NORM)**2
    design=np.column_stack([u**2,u**3])
    derivative=np.column_stack([4*r**3/NORM**4,6*r**5/NORM**6])
    powers=np.arange(4,4+2*len(coefficients),2)
    sag=sum(c*r**p for c,p in zip(coefficients,powers))
    slope=sum(c*p*r**(p-1) for c,p in zip(coefficients,powers))
    fits={}
    for mode in MODES:
        weight=np.sqrt(r/15.5) if mode=='area_sag' else np.ones(len(r))
        if mode=='edge_sag':weight=1+4*(r/15.5)**4
        a=design*weight[:,None];b=sag*weight
        if mode=='sag_slope':a=np.vstack([a,derivative*8]);b=np.r_[b,slope*8]
        normalized=np.linalg.lstsq(a,b,rcond=None)[0]
        fitted=design@normalized;fitted_slope=derivative@normalized
        fits[mode]={'coefficients_A4_A6':(normalized/NORM**np.array([4,6])).tolist(),
                    'normalized_coefficients':normalized.tolist(),
                    'reference_sag_rms_error_mm':float(np.sqrt(np.mean((fitted-sag)**2))),
                    'reference_sag_max_error_mm':float(np.max(abs(fitted-sag))),
                    'reference_slope_max_error':float(np.max(abs(fitted_slope-slope))),
                    'max_abs_fitted_departure_mm':float(np.max(abs(fitted))),
                    'max_abs_fitted_extra_slope':float(np.max(abs(fitted_slope)))}
    return fits

def initialize(seed,size,target):
    core.R=OUT
    core.initialize(seed,size,target,False,True)
    global FITS
    ss=core.sys.LDE.GetSurfaceAt(10)
    original=[ss.GetCellAt(i).DoubleValue for i in range(13,20)]
    FITS=fit_departure(original)
    core.POWERS=np.array([4,6]);core.NORM=NORM
    ss.Conic=0.;ss.GetCellAt(12).DoubleValue=0.
    for i in range(15,20):ss.GetCellAt(i).DoubleValue=0.
    core.sys.SystemData.TitleNotes.Title='Super-Symmar XL 150 R4 A6-only reverse candidate'
    core.sys.SystemData.TitleNotes.Notes='R4 new lower-order optimization. S10 Conic and A2 zero; A8/A10/A12/A14/A16 zero. Physical caps unchanged, full105deg, common f5.6 axis20 best image plane. See independent numerical deficits.'
    def apply(x):
        base=np.array(FITS[ACTIVE_MODE]['normalized_coefficients'])
        b=Polynomial(base).convert(kind=Legendre,domain=[0,1]).coef
        coefficients=Legendre(b+x[:2]*.025,domain=[0,1]).convert(kind=Polynomial).coef
        coefficients=np.pad(coefficients,(0,max(0,2-len(coefficients))))/NORM**np.array([4,6])
        ss.Conic=0.;ss.GetCellAt(12).DoubleValue=0.
        for i,v in zip([13,14],coefficients):ss.GetCellAt(i).DoubleValue=float(v)
        for i in range(15,20):ss.GetCellAt(i).DoubleValue=0.
        radii=core.base_r*(1+x[2:13]*.03)
        thickness=core.base_t+x[13:24]*.35
        for i,v in zip(core.RIDS,radii):core.sys.LDE.GetSurfaceAt(i).Radius=float(v)
        for i,v in zip(core.TIDS,thickness):core.sys.LDE.GetSurfaceAt(i).Thickness=float(v)
        core.sys.LDE.GetSurfaceAt(12).Thickness=float(core.base_focus)
        return coefficients,radii,thickness
    core.apply=apply

def evaluate(xx,mode,save=None):
    global ACTIVE_MODE
    ACTIVE_MODE=mode
    _,record=core.evaluate(np.r_[xx,0.],save)
    values=np.array(record['results_flat']);deficit=core.refs+.009-values
    positive=.006*np.logaddexp(0,deficit/.006)
    largest=float(np.max(deficit))
    smooth=largest+.012*np.log(np.mean(np.exp((deficit-largest)/.012)))
    fo=np.array(record['first_order'])
    limits=np.array([.7,.3,1.,.3,.7,1.,.7,.3,.7])
    violation=np.maximum(limits-np.array(record['geometry_gaps']),0)
    lag=record['image_distance_mm']-fo[1]
    residual=np.r_[positive**2/.065,8*max(0,smooth),(fo-[148.1,135.9,36.6,77.416])*[1.5,1.,.55,.35],
                   max(0,abs(record['chief_full_field_height_mm']-193)-.3)*.05,violation*8,
                   max(0,abs(lag)-.25)*.2,xx*.0001]
    surface=core.sys.LDE.GetSurfaceAt(10)
    actual=[surface.GetCellAt(i).DoubleValue for i in range(12,20)]
    assert actual[0]==0. and all(v==0. for v in actual[3:]) and surface.Conic==0.
    record.update(asphere_powers=[4,6],asphere_A4_A6=actual[1:3],A2=actual[0],A8_to_A16=actual[3:],
                  conic=float(surface.Conic),highest_nonzero_aspheric_power=6,fit_mode=mode,
                  fit_reference=FITS[mode],source_is_only_fitting_reference=True,
                  focus_minus_paraxial_bfl_mm=float(lag),optimizer='R4 A6-only fresh constrained optimization')
    record.pop('asphere_A4_to_A12',None)
    return residual.tolist(),record

def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',default=str(core.ROOT/'revision3'/'root_search'/'higher7_asphereonly1_best.zmx'))
    p.add_argument('--target',default=str(core.ROOT/'revision3'/'target_optimization.json'))
    p.add_argument('--name',default='a6_r2seed');p.add_argument('--size',type=int,default=128)
    p.add_argument('--iterations',type=int,default=20);p.add_argument('--max-jacobians',type=int,default=15)
    p.add_argument('--asphere-step',type=float,default=.003);p.add_argument('--macro-step',type=float,default=.04)
    a=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    count=0;jacobians=0;best=np.inf;bestx=np.zeros(24);begin=time.time()
    with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn'),initializer=initialize,
                             initargs=(a.seed,a.size,a.target)) as pool:
        seeds=[pool.submit(evaluate,np.zeros(24),m) for m in MODES]
        starts=[(m,job.result()) for m,job in zip(MODES,seeds)]
        for mode,(_,record) in starts:
            record.update(seed=a.seed,target=a.target,sampling=a.size)
            (OUT/(a.name+'_seed_'+mode+'.json')).write_text(json.dumps(record,indent=2))
            print('A6 fitted seed',mode,'max',record['max_shortfall'],'gap',record['geometry_gaps'][7],flush=True)
        valid=[(m,q) for m,q in starts if not q[1]['invalid_geometry']]
        if not valid:raise RuntimeError('No physically feasible A6 projection seed')
        mode=min(valid,key=lambda entry:entry[1][1]['max_shortfall']+.2*entry[1][1]['deficit_rms'])[0]
        def fun(x):
            nonlocal count,best,bestx
            if (OUT/(a.name+'.stop')).exists():raise StopIteration('Stop file requested')
            residual,record=pool.submit(evaluate,x,mode).result();count+=1
            fo=np.array(record['first_order'])
            feasible=not record['invalid_geometry'] and np.all(abs(fo-[148.1,135.9,36.6,77.416])<[.25,.4,.5,.6])
            score=record['max_shortfall']+.2*record['deficit_rms']
            record.update(eval=count,score=score,seed=a.seed,target=a.target,sampling=a.size,
                          seconds=time.time()-begin,cost=float(np.dot(residual,residual)))
            (OUT/(a.name+'_current.json')).write_text(json.dumps(record,indent=2))
            if feasible and score<best:
                best=score;bestx=x.copy()
                (OUT/(a.name+'_checkpoint.json')).write_text(json.dumps(record,indent=2))
                pool.submit(evaluate,x,mode,str(OUT/(a.name+'_best.zmx'))).result()
            print(a.name,count,'max',round(record['max_shortfall'],6),'score',round(best,6),
                  'first',np.round(fo,3),'gap',round(record['geometry_gaps'][7],4),'seconds',round(time.time()-begin),flush=True)
            return np.array(residual)
        def jac(x):
            nonlocal jacobians
            if jacobians>=a.max_jacobians:raise StopIteration('Jacobian budget reached')
            jacobians+=1;steps=np.r_[[a.asphere_step]*2,[a.macro_step]*22];jobs=[]
            for i,h in enumerate(steps):
                plus=x.copy();minus=x.copy();plus[i]+=h;minus[i]-=h
                jobs.append((pool.submit(evaluate,plus,mode),pool.submit(evaluate,minus,mode)))
            return np.array([(np.array(p.result()[0])-np.array(m.result()[0]))/(2*h) for (p,m),h in zip(jobs,steps)]).T
        low=np.r_[[-12.]*2,[-3.]*11,[-2.]*11];high=-low;low[19]=-2.5;high[19]=2.5
        try:
            res=least_squares(fun,np.zeros(24),jac=jac,bounds=(low,high),x_scale=1.,max_nfev=a.iterations,
                              ftol=2e-6,xtol=1e-7,gtol=1e-7)
            status=res.message
        except StopIteration as e:status=str(e)
        _,record=pool.submit(evaluate,bestx,mode,str(OUT/(a.name+'_best.zmx'))).result()
        record.update(status=status,score=best,seed=a.seed,target=a.target,sampling=a.size,seconds=time.time()-begin)
        (OUT/(a.name+'_result.json')).write_text(json.dumps(record,indent=2))
        print('FINISHED',a.name,'max',record['max_shortfall'],'A4/A6',record['asphere_A4_A6'],flush=True)

if __name__=='__main__':main()
