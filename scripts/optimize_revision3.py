"""Eight isolated ZOS-API workers; constrained finite-difference optimization."""
from pathlib import Path
import json, time, os, shutil, argparse
import numpy as np
from numpy.polynomial import Polynomial, Legendre
from scipy.optimize import least_squares, minimize_scalar
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'revision3'
RIDS = [1,2,3,4,5,6,8,9,10,11,12]
TIDS = [1,2,3,4,5,6,7,8,9,10,11]
POWERS = np.arange(4,13,2)
NORM = 15.5

def initialize(seed, size, target_path, minimax, axis_focus, close_focus=False, focus_weight=1.5):
    global app, sys, Z, analysis, settings, base_r, base_t, base_b, base_focus, indices, refs, target, caps, MINIMAX, AXIS_FOCUS, CLOSE_FOCUS, FOCUS_WEIGHT
    MINIMAX=minimax;AXIS_FOCUS=axis_focus;CLOSE_FOCUS=close_focus;FOCUS_WEIGHT=focus_weight
    namespace = {'__file__': str(ROOT/'scripts'/'probe_zos.py')}
    exec((ROOT/'scripts'/'probe_zos.py').read_text().split("print('system'")[0], namespace)
    app, sys, Z = (namespace[k] for k in ['app','sys','Z'])
    isolated = R / 'workers' / str(os.getpid())
    isolated.mkdir(parents=True, exist_ok=True)
    copy = isolated / 'seed.zmx'
    shutil.copy2(seed, copy)
    sys.LoadFile(str(copy), False)
    sys.Tools.RemoveAllVariables()
    sys.SystemData.Advanced.TurnOffThreading=True
    sys.SystemData.RayAiming.RayAiming=Z.SystemData.RayAimingMethod.Real
    caps = {int(k):v for k,v in json.loads((ROOT/'revision2'/'drawing_constraints.json').read_text())['clear_semidiameters_mm'].items()}
    for i,v in caps.items(): sys.LDE.GetSurfaceAt(i).MechanicalSemiDiameter = v
    base_r = np.array([sys.LDE.GetSurfaceAt(i).Radius for i in RIDS])
    base_t = np.array([sys.LDE.GetSurfaceAt(i).Thickness for i in TIDS])
    base_focus = sys.LDE.GetSurfaceAt(12).Thickness
    coeff = np.array([sys.LDE.GetSurfaceAt(10).GetCellAt(i).DoubleValue*NORM**p for i,p in zip(range(13,18),POWERS)])
    base_b = Polynomial(coeff).convert(kind=Legendre,domain=[0,1]).coef
    base_b = np.pad(base_b,(0,5-len(base_b)))
    indices = [sys.MFE.GetOperandValue(Z.Editors.MFE.MeritOperandType.INDX,i,1,0,0,0,0,0,0) for i in range(1,13)]
    target = json.loads(Path(target_path).read_text())
    refs = np.concatenate([np.array(target['data'][fn]).ravel() for fn in ['5.6','8','22']])
    analysis = sys.Analyses.New_FftMtf()
    settings = Z.Analysis.Settings.Mtf.IAS_FftMtf(analysis.GetSettings())
    settings.MaximumFrequency = 20
    settings.SampleSize = getattr(Z.Analysis.SampleSizes,f'S_{size}x{size}')

def apply(x):
    coefficients = Legendre(base_b+x[:5]*.03,domain=[0,1]).convert(kind=Polynomial).coef/NORM**POWERS
    for i,v in zip(range(13,18),coefficients): sys.LDE.GetSurfaceAt(10).GetCellAt(i).DoubleValue=float(v)
    rr = base_r*(1+x[5:16]*.03)
    tt = base_t+x[16:27]*.35
    for i,v in zip(RIDS,rr): sys.LDE.GetSurfaceAt(i).Radius=float(v)
    for i,v in zip(TIDS,tt): sys.LDE.GetSurfaceAt(i).Thickness=float(v)
    sys.LDE.GetSurfaceAt(12).Thickness=float(base_focus+x[27]*.35)
    return coefficients, rr, tt

def geometry(c):
    def sag(i,r):
        rad=sys.LDE.GetSurfaceAt(i).Radius
        if not np.isfinite(rad): return np.zeros_like(r)
        if np.max(abs(r))>=abs(rad): return np.full_like(r,np.nan)
        out=r*r/(rad*(1+np.sqrt(1-(r/rad)**2)))
        if i==10: out=out+sum(a*r**p for a,p in zip(c,POWERS))
        return out
    gaps=[]
    for i in [1,2,3,4,5,8,9,10,11]:
        radius=min(caps[i],caps[i+1])
        if i==10: radius=15.8
        r=np.linspace(0,radius,301)
        gap=sys.LDE.GetSurfaceAt(i).Thickness+sag(i+1,r)-sag(i,r)
        gaps.append(float(np.nanmin(gap)) if np.all(np.isfinite(gap)) else -100.)
    return gaps

def first_order():
    matrix=np.eye(2);old=1.;entry=0.
    for i in range(1,13):
        surface=sys.LDE.GetSurfaceAt(i);n=indices[i-1]
        matrix=np.array([[1.,0.],[-(n-old)/surface.Radius,1.]])@matrix
        if i==7: entry=matrix[0,1]/matrix[0,0]
        if i<12: matrix=np.array([[1.,surface.Thickness/n],[0.,1.]])@matrix
        old=n
    return [-1/matrix[1,0],-matrix[0,0]/matrix[1,0],entry,sum(sys.LDE.GetSurfaceAt(i).Thickness for i in range(1,12))]

def evaluate(x, save=None):
    c,rr,tt=apply(np.asarray(x))
    gaps=geometry(c)
    limits=[.7,.3,1.,.3,.7,1.,.7,.3,.7]
    violation=np.maximum(np.array(limits)-gaps,0)
    fo=first_order()
    # All physical apertures stay fixed. Invalid geometry is rejected before tracing.
    if np.any(violation>0):
        vals=np.zeros(refs.shape); invalid=True
    else:
        values=[];invalid=False
        if AXIS_FOCUS:
            sys.SystemData.Aperture.ApertureValue=148.1/5.6
            settings.Field.SetFieldNumber(1)
            def axis_cost(distance):
                sys.LDE.GetSurfaceAt(12).Thickness=float(distance)
                analysis.ApplyAndWaitForCompletion();data=analysis.GetResults().GetDataSeries(0)
                xx=np.array(list(data.XData.Data));yy=np.array(list(data.YData.Data)).reshape(data.YData.Data.GetLength(0),-1)
                return -float(np.interp(20,xx,yy[:,0]))
            try:
                focused=minimize_scalar(axis_cost,bracket=(fo[1]-.95,fo[1]-.55,fo[1]-.15),method='brent',options={'xtol':2e-7,'maxiter':25})
            except ValueError:
                focused=minimize_scalar(axis_cost,bounds=(fo[1]-1.4,fo[1]+.6),method='bounded',options={'xatol':2e-5,'maxiter':25})
            sys.LDE.GetSurfaceAt(12).Thickness=float(focused.x)
            settings.Field.UseAllFields()
        for fn in ['5.6','8','22']:
            fields=sys.SystemData.Fields
            hs=target.get('heights_by_aperture',{}).get(fn,target.get('heights',[])[:len(target['data'][fn])])
            sys.SystemData.Aperture.ApertureValue=148.1/float(fn)
            interior=[h for h in hs if 0<h<1]
            collected={}
            for offset in range(0,max(1,len(interior)),10):
                batch=[0]+interior[offset:offset+10]+[1]
                while fields.NumberOfFields>1:fields.RemoveField(fields.NumberOfFields)
                for h in batch[1:]:fields.AddField(0,float(np.degrees(np.arctan(h*193/148.1))) if h<1 else 52.5,1)
                assert fields.NumberOfFields==len(batch)
                analysis.ApplyAndWaitForCompletion();res=analysis.GetResults()
                for i,h in enumerate(batch):
                    d=res.GetDataSeries(i)
                    if d is None:collected[h]=[0.]*6;invalid=True;continue
                    xx=np.array(list(d.XData.Data));yy=np.array(list(d.YData.Data)).reshape(d.YData.Data.GetLength(0),-1)
                    collected[h]=[float(np.interp(f,xx,yy[:,j])) for f in [5,10,20] for j in [0,1]]
            values.extend(v for h in hs for v in collected[h])
        vals=np.nan_to_num(values,nan=0.,posinf=0.,neginf=0.)
    deficit=np.maximum(refs+.006-vals,0)
    # Higher than factory is free; emphasize the largest shortfalls.
    optical=deficit**2/.05 if MINIMAX else deficit**1.5/.15
    chief_height=sys.MFE.GetOperandValue(Z.Editors.MFE.MeritOperandType.REAY,13,1,0,1,0,0,0,0) if not invalid else 0.
    focus_lag=float(sys.LDE.GetSurfaceAt(12).Thickness)-fo[1]
    residual=np.r_[optical, np.max(deficit)*(10. if MINIMAX else 0.), (np.array(fo)-[148.1,135.9,36.6,77.416])*np.array([2.,1.5,.8,.5]),max(0,abs(chief_height-193)-.3)*.05,max(0,abs(focus_lag)-.15)*FOCUS_WEIGHT if CLOSE_FOCUS else 0.,violation*5,np.asarray(x)*.00015]
    record={'x':list(map(float,x)),'results_flat':list(map(float,vals)),'max_shortfall':float(np.max(refs-vals)),'deficit_rms':float(np.sqrt(np.mean(np.maximum(refs-vals,0)**2))),'first_order':list(map(float,fo)),'geometry_gaps':gaps,'asphere_A4_to_A12':c.tolist(),'invalid_geometry':invalid,'chief_full_field_height_mm':float(chief_height),'image_distance_mm':float(sys.LDE.GetSurfaceAt(12).Thickness),'axis_focus_enforced':AXIS_FOCUS,'ray_aiming_method':str(sys.SystemData.RayAiming.RayAiming),'best_focus_minus_paraxial_bfl_mm':focus_lag,'close_focus_regularization':CLOSE_FOCUS}
    if save:
        fields=sys.SystemData.Fields
        while fields.NumberOfFields>1:fields.RemoveField(fields.NumberOfFields)
        for h in [0.2,0.4,0.6,0.68,0.8,1.]:fields.AddField(0,float(np.degrees(np.arctan(h*193/148.1))) if h<1 else 52.5,1)
        sys.SystemData.Aperture.ApertureValue=148.1/5.6
        sys.SaveAs(str(save))
    return residual.tolist(),record

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seed',default=str(ROOT/'revision2'/'SuperSymmarXL_150_R2_f5p6.zmx'));parser.add_argument('--target',default=str(ROOT/'analysis'/'target_manual.json'));parser.add_argument('--iterations',type=int,default=65);parser.add_argument('--size',type=int,default=128);parser.add_argument('--name',default='search1');parser.add_argument('--start',default=None);parser.add_argument('--minimax',action='store_true');parser.add_argument('--scale',choices=['jac','unit'],default='unit');parser.add_argument('--axis-focus',action='store_true');parser.add_argument('--step',type=float,default=.02);parser.add_argument('--workers',type=int,default=8);parser.add_argument('--close-focus',action='store_true');parser.add_argument('--focus-weight',type=float,default=1.5)
    args=parser.parse_args();R.mkdir(exist_ok=True)
    start=time.time();count=0;best=np.inf;bestx=np.zeros(28);best_record=None
    if args.start:bestx=np.array(json.loads(Path(args.start).read_text())['x'])
    x0=bestx.copy();steps=np.full(28,args.step)
    assert 1<=args.workers<=8
    with ProcessPoolExecutor(max_workers=args.workers,mp_context=mp.get_context('spawn'),initializer=initialize,initargs=(args.seed,args.size,args.target,args.minimax,args.axis_focus,args.close_focus,args.focus_weight)) as pool:
        identical=[pool.submit(evaluate,x0) for _ in range(args.workers)]
        checks=np.array([job.result()[0] for job in identical])
        spread=float(np.max(np.ptp(checks,axis=0)))
        print(f'{args.workers}-worker identical-input residual spread',spread,flush=True)
        assert spread<1e-8,'Worker evaluation is not deterministic'
        def fun(x):
            nonlocal count,best,bestx,best_record
            residual,record=pool.submit(evaluate,x).result();count+=1
            (R/f'{args.name}_current.json').write_text(json.dumps(dict(record,eval=count,cost=float(np.dot(residual,residual)),seconds=time.time()-start,seed=args.seed,target=args.target,sampling=args.size),indent=2))
            efl,bfl,ep,track=record['first_order']
            score=record['max_shortfall']+.2*record['deficit_rms']
            feasible=not record['invalid_geometry'] and abs(efl-148.1)<.25 and abs(bfl-135.9)<.4 and abs(ep-36.6)<.5 and abs(track-77.416)<.6
            if feasible and score<best:
                best=score;bestx=x.copy();best_record=record
                (R/f'{args.name}_checkpoint.json').write_text(json.dumps(dict(record,eval=count,seconds=time.time()-start,score=score,seed=args.seed,target=args.target,sampling=args.size),indent=2))
            if count%4==1:print(args.name,count,'shortfall',round(record['max_shortfall'],5),'best',round(best,5),'first-order',np.round(record['first_order'],3),'seconds',round(time.time()-start),flush=True)
            return np.array(residual)
        def jac(x):
            f0=fun(x);jobs=[]
            for i,h in enumerate(steps):
                xp=x.copy();xp[i]+=h;jobs.append(pool.submit(evaluate,xp))
            return np.array([(np.array(job.result()[0])-f0)/h for job,h in zip(jobs,steps)]).T
        # Radius range +/-9%; thickness/spacing range limited by physical feasibility.
        low=np.r_[np.full(5,-12.),np.full(11,-3.),np.full(11,-2.),-5.]
        high=np.r_[np.full(5,12.),np.full(11,3.),np.full(11,2.),5.]
        low[22]=-2.5;high[22]=2.5
        res=least_squares(fun,x0,jac=jac,bounds=(low,high),x_scale='jac' if args.scale=='jac' else 1.,max_nfev=args.iterations,ftol=1e-6,xtol=1e-7,gtol=1e-7,diff_step=.001)
        final=pool.submit(evaluate,bestx,str(R/f'{args.name}_best.zmx')).result()[1]
        (R/f'{args.name}_result.json').write_text(json.dumps(dict(final,status=res.message,score=best,seed=args.seed,target=args.target,sampling=args.size,seconds=time.time()-start),indent=2))
        optimized=pool.submit(evaluate,res.x,str(R/f'{args.name}_optimized.zmx')).result()[1]
        (R/f'{args.name}_optimized.json').write_text(json.dumps(dict(optimized,status=res.message,seed=args.seed,target=args.target,sampling=args.size,seconds=time.time()-start),indent=2))
        print('FINISHED',args.name,'max shortfall',final['max_shortfall'],'seconds',round(time.time()-start),flush=True)

if __name__=='__main__': main()
