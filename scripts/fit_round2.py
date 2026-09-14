from pathlib import Path
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
import numpy as np,json,time
from scipy.optimize import least_squares
sys.LoadFile(str(ROOT/'models'/'axis_optimized.zmx'),False)
sys.Tools.RemoveAllVariables()
for h in [38.6,77.2,115.8,131.24,154.4,193]:sys.SystemData.Fields.AddField(0,h,1)
# rows: relative image height; columns T5,S5,T10,S10,T20,S20.
target={5.6:[[.90,.90,.79,.79,.64,.64],[.66,.80,.47,.59,.32,.40],[.48,.68,.28,.41,.055,.28],[.42,.58,.215,.32,.07,.235],[.40,.54,.21,.29,.09,.21]],8:[[.94,.94,.865,.865,.69,.69],[.80,.92,.60,.78,.39,.57],[.67,.79,.41,.57,.14,.40],[.54,.53,.30,.35,.14,.26],[.48,.45,.27,.29,.12,.22]],22:[[.905,.905,.82,.82,.66,.66],[.90,.90,.77,.815,.62,.655],[.87,.89,.705,.80,.485,.63],[.78,.87,.545,.77,.30,.59],[.72,.85,.455,.72,.19,.51],[.615,.82,.34,.64,.07,.39],[.45,.74,.20,.485,.03,.24]]}
(ROOT/'analysis'/'target_manual.json').write_text(json.dumps({'note':'Manual approximate digitization of supplied Schneider PDF p2 infinity row; ~0.02-0.04 uncertainty; T dashed, S radial solid','heights':[0,.2,.4,.6,.68,.8,1.0],'data':target},indent=2))
a=sys.Analyses.New_FftMtf();sett=Z.Analysis.Settings.Mtf.IAS_FftMtf(a.GetSettings());sett.MaximumFrequency=20;sett.SampleSize=Z.Analysis.SampleSizes.S_128x128
# Scaled variables: A4,A6,A8,focus, stop position, radius deltas on 3,4,5,6,8,9,10,11,12.
asph=sys.LDE.GetSurfaceAt(10);base_r={i:sys.LDE.GetSurfaceAt(i).Radius for i in [1,2,3,4,5,6,8,9,10,11,12]}
x0=np.array([asph.GetCellAt(i).DoubleValue/s for i,s in zip([13,14,15],[1e-6,1e-9,1e-12])]+[sys.LDE.GetSurfaceAt(12).Thickness,3.03]+[0]*len(base_r))
x0=np.array(json.loads((ROOT/'analysis'/'fit_round1.json').read_text())['x'])
bounds=([-30,-100,-100,132,.4]+[-.03]*len(base_r),[30,100,100,140,5.66]+[.03]*len(base_r))
def apply(x):
 for i,s,v in zip([13,14,15],[1e-6,1e-9,1e-12],x):asph.GetCellAt(i).DoubleValue=float(v*s)
 sys.LDE.GetSurfaceAt(12).Thickness=float(x[3]);sys.LDE.GetSurfaceAt(6).Thickness=float(x[4]);sys.LDE.GetSurfaceAt(7).Thickness=6.06-float(x[4])
 for (i,r),v in zip(base_r.items(),x[5:]):sys.LDE.GetSurfaceAt(i).Radius=r*(1+float(v))
def calc(fn):
 sys.SystemData.Aperture.ApertureValue=148.1/fn
 a.ApplyAndWaitForCompletion();res=a.GetResults();out=[]
 for i in range(len(target[fn])):
  d=res.GetDataSeries(i);xx=np.array(list(d.XData.Data));yy=np.array(list(d.YData.Data)).reshape(d.YData.Data.GetLength(0),-1)
  out.append([np.interp(f,xx,yy[:,j]) for f in [5,10,20] for j in range(2)])
 return np.array(out)
count=0;best=100;start=time.time()
def fun(x):
 global count,best
 apply(x);res=[]
 for fn in target:res.extend((calc(fn)-np.array(target[fn])).ravel())
 # Maintain published first-order constraints while allowing prescription refinement.
 efl=sys.MFE.GetOperandValue(Z.Editors.MFE.MeritOperandType.EFFL,0,1,0,0,0,0,0,0)
 res.extend([(efl-148.1)*.1,(x[3]-135.9)*.025]);res.extend(x[5:]*.3)
 res=np.array(res);err=float(np.sqrt(np.mean(res[:102]**2)));count+=1
 if err<best:
  best=err;(ROOT/'analysis'/'fit_checkpoint.json').write_text(json.dumps({'x':x.tolist(),'base_r':base_r,'rmse_progress':best,'eval':count,'seconds':time.time()-start},indent=2))
 if count%20==1:print('eval',count,'best',best,'seconds',round(time.time()-start),flush=True)
 return res
r=least_squares(fun,x0,bounds=bounds,diff_step=.01,x_scale='jac',max_nfev=120,verbose=0,ftol=1e-6,xtol=1e-7)
apply(r.x)
outputs={str(fn):calc(fn).tolist() for fn in target}
(ROOT/'analysis'/'fit_result.json').write_text(json.dumps({'x':r.x.tolist(),'base_r':base_r,'outputs':outputs,'cost':r.cost,'message':r.message},indent=2))
sys.SystemData.Aperture.ApertureValue=148.1/5.6
sys.SaveAs(str(ROOT/'models'/'SuperSymmarXL_150_f5p6_reverse.zmx'));a.Close();app.CloseApplication()
