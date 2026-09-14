from pathlib import Path
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
import numpy as np,json,time
from scipy.optimize import least_squares
sys.LoadFile(str(ROOT/'models'/'axis_optimized.zmx'),False);sys.Tools.RemoveAllVariables()
sys.LDE.GetSurfaceAt(6).Thickness=4.839901032096402;sys.LDE.GetSurfaceAt(7).Thickness=6.06-4.839901032096402
for h in [38.6,77.2,115.8,131.24,154.4,193]:sys.SystemData.Fields.AddField(0,h,1)
tar=json.loads((ROOT/'analysis'/'target_manual.json').read_text());target=tar['data']
a=sys.Analyses.New_FftMtf();sett=Z.Analysis.Settings.Mtf.IAS_FftMtf(a.GetSettings());sett.MaximumFrequency=20;sett.SampleSize=Z.Analysis.SampleSizes.S_128x128
asph=sys.LDE.GetSurfaceAt(10);scales=np.array([1e-6,1e-9,1e-12,1e-15,1e-18])
x0=np.r_[[asph.GetCellAt(i).DoubleValue/scale for i,scale in zip(range(13,18),scales)],135.85]
def apply(x):
 for i,scale,xx in zip(range(13,18),scales,x):asph.GetCellAt(i).DoubleValue=float(xx*scale)
 sys.LDE.GetSurfaceAt(12).Thickness=float(x[-1])
def calc(fn):
 sys.SystemData.Aperture.ApertureValue=148.1/float(fn);a.ApplyAndWaitForCompletion();res=a.GetResults();out=[]
 for i in range(len(target[fn])):
  d=res.GetDataSeries(i);xx=np.array(list(d.XData.Data));yy=np.array(list(d.YData.Data)).reshape(d.YData.Data.GetLength(0),-1)
  out.append([np.interp(f,xx,yy[:,j]) for f in [5,10,20] for j in range(2)])
 return np.array(out)
count=0;best=1;start=time.time()
def fun(x):
 global count,best
 apply(x);err=np.concatenate([(calc(fn)-target[fn]).ravel() for fn in target]);count+=1;rmse=float(np.sqrt(np.mean(err**2)))
 if rmse<best:
  best=rmse;(ROOT/'analysis'/'physical_checkpoint.json').write_text(json.dumps({'x':x.tolist(),'rmse':best,'count':count},indent=2))
 if count%20==1:print('physical',count,best,round(time.time()-start),flush=True)
 return err
steps=np.array([.0001,.001,.002,.01,.02,.001])
def jac(x):
 columns=[]
 for i,h in enumerate(steps):
  xp=x.copy();xm=x.copy();xp[i]+=h;xm[i]-=h;columns.append((fun(xp)-fun(xm))/(2*h))
 return np.array(columns).T
r=least_squares(fun,x0,jac=jac,x_scale=[1,2,5,10,10,.3],bounds=([-30,-100,-100,-100,-100,134],[30,100,100,100,100,137]),max_nfev=45,ftol=1e-6,xtol=1e-8)
apply(r.x);out={fn:calc(fn).tolist() for fn in target}
(ROOT/'analysis'/'physical_result.json').write_text(json.dumps({'x':r.x.tolist(),'outputs':out,'cost':r.cost,'message':r.message},indent=2));sys.SystemData.Aperture.ApertureValue=148.1/5.6
sys.SaveAs(str(ROOT/'models'/'physical_constrained.zmx'));a.Close();app.CloseApplication()
