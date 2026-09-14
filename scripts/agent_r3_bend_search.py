"""Four power-preserving singlet bends plus seven asphere basis parameters."""
from pathlib import Path
import argparse,json,time,multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from scipy.optimize import least_squares
import agent_r3_smooth_search as search

OUT=search.OUT
PAIRS=[(1,2),(3,4),(5,6),(11,12)]
SCALES=np.array([.0003,.0005,.0005,.0003])

def initialize(seed,size,target):
    search.initialize(seed,size,target,'smoothmax',True)
    global NI,WEIGHTS
    NI=np.array([[search.core.sys.MFE.GetOperandValue(search.core.Z.Editors.MFE.MeritOperandType.INDX,i,w,0,0,0,0,0,0)
                  for i in range(1,13)] for w in range(1,7)])
    WEIGHTS=np.array([search.core.sys.SystemData.Wavelengths.GetWavelength(w).Weight for w in range(1,7)])
    WEIGHTS=WEIGHTS/WEIGHTS.sum()

def evaluate(y,save=None):
    c=search.core
    radii=c.base_r.copy()
    for (front,back),delta in zip(PAIRS,y[7:]*SCALES):
        j=c.RIDS.index(front);k=c.RIDS.index(back)
        n=c.indices[front-1];alpha=n-1.;beta=c.base_t[c.TIDS.index(front)]/n*alpha**2
        c1=1/radii[j];c2=1/radii[k]
        power=alpha*(c1-c2)+beta*c1*c2
        newc1=c1+delta;newc2=(power-alpha*newc1)/(-alpha+beta*newc1)
        radii[j]=1/newc1;radii[k]=1/newc2
    relative=radii/c.base_r-1.
    xx=np.r_[y[:7],relative/.03,np.zeros(11)]
    residual,record=search.evaluate(xx,save)
    distances=[]
    for nn in NI:
        matrix=np.eye(2);old=1.
        for i in range(1,13):
            ss=c.sys.LDE.GetSurfaceAt(i);n=nn[i-1]
            matrix=np.array([[1.,0.],[-(n-old)/ss.Radius,1.]])@matrix
            if i<12:matrix=np.array([[1.,ss.Thickness/n],[0.,1.]])@matrix
            old=n
        distances.append(-matrix[0,0]/matrix[1,0])
    distances=np.array(distances);mean=float(WEIGHTS@distances)
    std=float(np.sqrt(WEIGHTS@(distances-mean)**2))
    lag=record['image_distance_mm']-record['first_order'][1]
    residual=np.r_[residual,max(0,std-.22)*1.,max(0,abs(lag)-.25)*.35,
                   max(0,np.max(abs(relative))-.09)*15.]
    record.update(bend_parameters=y[7:].tolist(),bend_curvature_scales=SCALES.tolist(),
                  reduced_x=y.tolist(),maximum_relative_radius_change=float(np.max(abs(relative))),
                  six_wave_bfl_mm=distances.tolist(),weighted_bfl_std_mm=std,
                  weighted_bfl_mean_mm=mean,bfl_span_mm=float(np.ptp(distances)),
                  focus_minus_paraxial_bfl_mm=float(lag))
    return residual.tolist(),record

def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',default=str(OUT/'higher7_asphereonly1_best.zmx'))
    p.add_argument('--target',default=str(search.core.ROOT/'revision3'/'target_optimization.json'))
    p.add_argument('--name',default='bend7_1');p.add_argument('--size',type=int,default=256)
    p.add_argument('--iterations',type=int,default=18);p.add_argument('--max-jacobians',type=int,default=4)
    a=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    count=0;jacs=0;best=np.inf;besty=np.zeros(11);begin=time.time()
    with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn'),initializer=initialize,
                             initargs=(a.seed,a.size,a.target)) as pool:
        def fun(y):
            nonlocal count,best,besty
            if (OUT/(a.name+'.stop')).exists():raise StopIteration('Stop file requested')
            residual,record=pool.submit(evaluate,y).result();count+=1
            fo=np.array(record['first_order'])
            feasible=not record['invalid_geometry'] and np.all(abs(fo-[148.1,135.9,36.6,77.416])<[.25,.4,.5,.6]) and record['maximum_relative_radius_change']<=.09
            score=record['max_shortfall']+.2*record['deficit_rms']
            record.update(eval=count,score=score,seed=a.seed,target=a.target,sampling=a.size,
                          mode='smoothmax',seconds=time.time()-begin,cost=float(np.dot(residual,residual)))
            (OUT/(a.name+'_current.json')).write_text(json.dumps(record,indent=2))
            if feasible and score<best:
                best=score;besty=y.copy()
                (OUT/(a.name+'_checkpoint.json')).write_text(json.dumps(record,indent=2))
                pool.submit(evaluate,y,str(OUT/(a.name+'_best.zmx'))).result()
            print(a.name,count,'max',round(record['max_shortfall'],6),'score',round(best,6),
                  'ca',round(record['weighted_bfl_std_mm'],4),'lag',round(record['focus_minus_paraxial_bfl_mm'],4),
                  'seconds',round(time.time()-begin),flush=True)
            return np.array(residual)
        def jac(y):
            nonlocal jacs
            if jacs>=a.max_jacobians:raise StopIteration('Jacobian budget reached')
            jacs+=1;jobs=[];steps=[.002]*7+[.02]*4
            for i,h in enumerate(steps):
                plus=y.copy();minus=y.copy();plus[i]+=h;minus[i]-=h
                jobs.append((pool.submit(evaluate,plus),pool.submit(evaluate,minus)))
            return np.array([(np.array(p.result()[0])-np.array(m.result()[0]))/(2*h) for (p,m),h in zip(jobs,steps)]).T
        try:
            r=least_squares(fun,np.zeros(11),jac=jac,bounds=(np.r_[np.full(7,-5.),np.full(4,-1.5)],np.r_[np.full(7,5.),np.full(4,1.5)]),
                            x_scale=1.,max_nfev=a.iterations,ftol=2e-6,xtol=1e-7,gtol=1e-7)
            status=r.message
        except StopIteration as e:status=str(e)
        _,rec=pool.submit(evaluate,besty,str(OUT/(a.name+'_best.zmx'))).result()
        rec.update(status=status,score=best,seed=a.seed,target=a.target,sampling=a.size,mode='smoothmax',seconds=time.time()-begin)
        (OUT/(a.name+'_result.json')).write_text(json.dumps(rec,indent=2))
        print('FINISHED',a.name,'maximum deficit',rec['max_shortfall'],flush=True)

if __name__=='__main__':main()
