from pathlib import Path
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
import numpy as np,time,json
from scipy.optimize import minimize_scalar
R=ROOT/'revision3';sys.LoadFile(str(R/'macro_parallel1_best.zmx'),False)
sys.SystemData.Aperture.ApertureValue=148.1/5.6
sys.SystemData.RayAiming.RayAiming=Z.SystemData.RayAimingMethod.Real
a=sys.Analyses.New_FftMtf();s=Z.Analysis.Settings.Mtf.IAS_FftMtf(a.GetSettings());s.MaximumFrequency=20;s.SampleSize=Z.Analysis.SampleSizes.S_256x256;s.Field.SetFieldNumber(1)
tick=time.time();a.ApplyAndWaitForCompletion();d=a.GetResults().GetDataSeries(0);xx=np.array(list(d.XData.Data));yy=np.array(list(d.YData.Data)).reshape(d.YData.Data.GetLength(0),-1)
out={'fft256':float(np.interp(20,xx,yy[:,0])),'fft256_seconds':time.time()-tick,'operand_trials':[]}
for sampling in range(1,7):
 tick=time.time()
 try:value=sys.MFE.GetOperandValue(Z.Editors.MFE.MeritOperandType.MTFT,sampling,0,1,20,0,0,0,0)
 except Exception as exc:value=str(exc)
 out['operand_trials'].append({'sampling':sampling,'value':value,'seconds':time.time()-tick})
out['focus_trials']=[]
for method in ['MTFT3','MTFT4','FFT256']:
 tick=time.time()
 def cost(distance):
  sys.LDE.GetSurfaceAt(12).Thickness=float(distance)
  if method.startswith('MTFT'):return -sys.MFE.GetOperandValue(Z.Editors.MFE.MeritOperandType.MTFT,int(method[-1]),0,1,20,0,0,0,0)
  a.ApplyAndWaitForCompletion();data=a.GetResults().GetDataSeries(0);xd=np.array(list(data.XData.Data));yd=np.array(list(data.YData.Data)).reshape(data.YData.Data.GetLength(0),-1)
  return -float(np.interp(20,xd,yd[:,0]))
 root=minimize_scalar(cost,bounds=(134.5,136.5),method='bounded',options={'xatol':2e-6})
 out['focus_trials'].append({'method':method,'image_distance_mm':float(root.x),'axis20_mtf':float(-root.fun),'seconds':time.time()-tick,'evals':root.nfev})
print(json.dumps(out,indent=2),flush=True);(R/'fast_axis_probe.json').write_text(json.dumps(out,indent=2))
a.Close();app.CloseApplication()
