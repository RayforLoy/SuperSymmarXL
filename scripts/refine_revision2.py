from pathlib import Path
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
import numpy as np,json,time
from numpy.polynomial import Polynomial,Legendre
from scipy.optimize import least_squares
R=ROOT/'revision2';sys.LoadFile(str(R/'SuperSymmarXL_150_R2.zmx'),False)
sys.SystemData.Fields.GetField(7).Y=52.5
asph=sys.LDE.GetSurfaceAt(10);norm=15.5
powers=np.arange(4,13,2)
cp=np.array([asph.GetCellAt(i).DoubleValue*norm**p for i,p in zip(range(13,18),powers)])
b0=Polynomial(cp).convert(kind=Legendre,domain=[0,1]).coef
rids=[1,2,3,4,5,6,8,9,10,11,12]
base_r=np.array([sys.LDE.GetSurfaceAt(i).Radius for i in rids])
base_n=np.array([sys.MFE.GetOperandValue(Z.Editors.MFE.MeritOperandType.INDX,i,1,0,0,0,0,0,0) for i in range(1,13)])
x0=np.r_[b0,sys.LDE.GetSurfaceAt(12).Thickness,np.zeros(11)]
def para():
 M=np.eye(2);old=1;ep=0
 for i in range(1,13):
  ss=sys.LDE.GetSurfaceAt(i);nn=base_n[i-1];M=np.array([[1,0],[-(nn-old)/ss.Radius,1]])@M
  if i==7:ep=M[0,1]/M[0,0]
  if i<12:M=np.array([[1,ss.Thickness/nn],[0,1]])@M
  old=nn
 return -1/M[1,0],-M[0,0]/M[1,0],ep

target=json.loads((ROOT/'analysis/target_manual.json').read_text())['data']
a=sys.Analyses.New_FftMtf();settings=Z.Analysis.Settings.Mtf.IAS_FftMtf(a.GetSettings());settings.MaximumFrequency=20;settings.SampleSize=Z.Analysis.SampleSizes.S_128x128

def apply(x):
 c=Legendre(x[:5],domain=[0,1]).convert(kind=Polynomial).coef/norm**powers
 for i,v in zip(range(13,18),c):asph.GetCellAt(i).DoubleValue=float(v)
 sys.LDE.GetSurfaceAt(12).Thickness=float(x[5])
 for i,rr,vv in zip(rids,base_r,x[6:]):sys.LDE.GetSurfaceAt(i).Radius=float(rr*(1+vv))
 return c

def geom(c):
 rr=np.linspace(0,14.3,151)
 def sag(rad):return rr**2/(rad*(1+np.sqrt(1-(rr/rad)**2)))
 added=sum(v*rr**p for v,p in zip(c,powers))
 gap=.99+sag(sys.LDE.GetSurfaceAt(11).Radius)-sag(asph.Radius)-added
 glass=4.7+sag(asph.Radius)+added-sag(sys.LDE.GetSurfaceAt(9).Radius)
 return float(min(gap)),float(min(glass))

def calc(fn):
 sys.SystemData.Aperture.ApertureValue=148.1/float(fn);a.ApplyAndWaitForCompletion();res=a.GetResults();out=[]
 for i in range(len(target[fn])):
  d=res.GetDataSeries(i)
  if d is None:return np.zeros((len(target[fn]),6))
  xx=np.array(list(d.XData.Data));yy=np.array(list(d.YData.Data)).reshape(d.YData.Data.GetLength(0),-1)
  out.append([np.interp(f,xx,yy[:,j]) for f in [5,10,20] for j in [0,1]])
 return np.array(out)
count=0;best=1;start=time.time();bestx=x0.copy()
def fun(x):
 global count,best,bestx
 c=apply(x);gap,glass=geom(c);count+=1
 # Infeasible trials are rejected before optical evaluation; never saved as candidates.
 if gap<.25 or glass<1:
  bad=max(.25-gap,1-glass,0)
  return np.r_[np.full(102,1+bad),np.zeros(102),bad*20,np.zeros(14)]
 vals=np.concatenate([calc(fn).ravel() for fn in target]);refs=np.concatenate([np.array(target[fn]).ravel() for fn in target])
 deficit=np.maximum(refs-vals,0);efl,bfl,ep=para();rms=float(np.sqrt(np.mean(deficit**2)));score=float(max(deficit)+.2*rms)
 if score<best and abs(efl-148.1)<.1 and abs(bfl-135.9)<.15 and abs(ep-36.6)<.2:
  best=score;bestx=x.copy();(R/'refinement_checkpoint.json').write_text(json.dumps({'x':x.tolist(),'A4_to_A12':c.tolist(),'deficit_rmse':rms,'score':best,'efl':efl,'bfl':bfl,'entrance_pupil':ep,'max_deficit':float(max(deficit)),'minimum_air_gap_mm':gap,'eval':count,'seconds':time.time()-start},indent=2))
 if count%20==1:print('R2',count,'deficit rms',round(best,5),'gap',round(gap,4),'elapsed',round(time.time()-start),flush=True)
 return np.r_[np.maximum(refs+.01-vals,0)**2/.1,.015*(vals-refs),max(0,.35-gap)*2,max(0,abs(efl-148.1)-.05)*5,max(0,abs(bfl-135.9)-.08)*5,max(0,abs(ep-36.6)-.1)*2,x[6:]*.1]
steps=np.array([2e-5]*5+[.001]+[5e-6]*11)
def jac(x):
 cols=[];f0=fun(x)
 for i,h in enumerate(steps):
  xp=x.copy();xp[i]+=h;cols.append((fun(xp)-f0)/h)
 return np.array(cols).T
res=least_squares(fun,x0,jac=jac,bounds=([-.8]*5+[134.5]+[-.03]*11,[.8]*5+[137]+[.03]*11),x_scale=[.01]*5+[.1]+[.01]*11,max_nfev=25,ftol=1e-5,xtol=1e-6)
c=apply(bestx);out={fn:calc(fn).tolist() for fn in target}
sys.SystemData.Aperture.ApertureValue=148.1/5.6;sys.LDE.GetSurfaceAt(1).Comment='R2 drawing-constrained candidate; full 105 degree field; verify report'
sys.SaveAs(str(R/'SuperSymmarXL_150_R2_refined.zmx'));(R/'refinement.json').write_text(json.dumps({'x':bestx.tolist(),'A4_to_A12':c.tolist(),'results':out,'status':res.message,'minimum_gap_mm':geom(c)[0]},indent=2));a.Close();app.CloseApplication()
