"""Fast first-order dispersion correction; all proposed seeds then natively traced."""
from pathlib import Path
import argparse,json,time,numpy as np
from scipy.optimize import least_squares
import optimize_revision3 as core

parser=argparse.ArgumentParser();parser.add_argument('--seed',default=str(core.R/'focus_gap_physical_seed.zmx'));parser.add_argument('--name',default='achromatic_seed1');args=parser.parse_args()
core.initialize(args.seed,128,str(core.R/'target_optimization.json'),True,True)
try:
 index=np.array([[core.sys.MFE.GetOperandValue(core.Z.Editors.MFE.MeritOperandType.INDX,i,w,0,0,0,0,0,0) for i in range(1,13)] for w in range(1,7)])
 weights=np.array([core.sys.SystemData.Wavelengths.GetWavelength(w).Weight for w in range(1,7)]);weights/=weights.sum()
 coeff=core.Legendre(core.base_b,domain=[0,1]).convert(kind=core.Polynomial).coef/core.NORM**core.POWERS
 cap=core.caps;start=time.time()
 def prescription(x):
  rr=dict(zip(core.RIDS,core.base_r*(1+x[:11]*.03)));rr[7]=np.inf
  tt=dict(zip(core.TIDS,core.base_t+x[11:]*.35))
  return rr,tt
 def first_order(rr,tt):
  out=[]
  for indices in index:
   matrix=np.eye(2);old=1;entry=0
   for i in range(1,13):
    n=indices[i-1];matrix=np.array([[1,0],[-(n-old)/rr[i],1]])@matrix
    if i==7:entry=matrix[0,1]/matrix[0,0]
    if i<12:matrix=np.array([[1,tt[i]/n],[0,1]])@matrix
    old=n
   out.append([-1/matrix[1,0],-matrix[0,0]/matrix[1,0],entry,sum(tt.values())])
  return np.array(out)
 def geometry(rr,tt):
  def sag(i,r):
   if np.max(r)>=abs(rr[i]):return np.full_like(r,np.nan)
   result=r*r/(rr[i]*(1+np.sqrt(1-(r/rr[i])**2)))
   if i==10:result+=sum(a*r**p for a,p in zip(coeff,core.POWERS))
   return result
  gaps=[]
  for i in [1,2,3,4,5,8,9,10,11]:
   radius=15.8 if i==10 else min(cap[i],cap[i+1]);r=np.linspace(0,radius,1001)
   gap=tt[i]+sag(i+1,r)-sag(i,r)
   gaps.append(float(min(gap)) if np.all(np.isfinite(gap)) else -100)
  return gaps
 def fun(x):
  rr,tt=prescription(x);fo=first_order(rr,tt);gaps=geometry(rr,tt)
  return np.r_[(fo[0]-[148.1,135.9,36.6,77.416])*[15,15,5,5],(fo[:,1]-135.9)*np.sqrt(weights)*5,np.maximum(np.array([.7,.3,1,.3,.7,1,.7,.3,.7])+.05-gaps,0)*100,x*.0008]
 before=first_order(*prescription(np.zeros(22)))
 res=least_squares(fun,np.zeros(22),bounds=(np.r_[np.full(11,-3.),np.full(11,-2.)],np.r_[np.full(11,3.),np.full(11,2.)]),max_nfev=200,ftol=1e-9,xtol=1e-9,gtol=1e-9)
 rr,tt=prescription(res.x);after=first_order(rr,tt)
 x=np.r_[np.zeros(5),res.x,0]
 residual,native=core.evaluate(x,str(core.R/(args.name+'.zmx')))
 out=dict(native,seed=args.seed,target=str(core.R/'target_optimization.json'),sampling=128,first_order_by_wavelength_before=before.tolist(),first_order_by_wavelength_after=after.tolist(),weighted_bfl_std_before_mm=float(np.sqrt(np.dot(weights,(before[:,1]-np.dot(weights,before[:,1]))**2))),weighted_bfl_std_after_mm=float(np.sqrt(np.dot(weights,(after[:,1]-np.dot(weights,after[:,1]))**2))),status=res.message,seconds=time.time()-start)
 (core.R/(args.name+'.json')).write_text(json.dumps(out,indent=2))
 print('Achromatic seed native audit',args.name,'CA std before/after',out['weighted_bfl_std_before_mm'],out['weighted_bfl_std_after_mm'],'max MTF shortfall',native['max_shortfall'],'firstorder',native['first_order'],flush=True)
finally:core.app.CloseApplication()
