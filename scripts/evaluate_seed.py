from pathlib import Path
exec(open(str(Path(__file__).with_name('probe_zos.py'))).read().split("print('system'")[0])
import numpy as np,json,time
sys.LoadFile(str(ROOT/'models'/'seed_optimized.zmx'),False)
sys.SystemData.RayAiming.RayAiming=Z.SystemData.RayAimingMethod.Real
# Limit full-aperture field to manufacturer's published range.
while sys.SystemData.Fields.NumberOfFields>8:sys.SystemData.Fields.RemoveField(sys.SystemData.Fields.NumberOfFields)
a=sys.Analyses.New_FftMtf();sett=Z.Analysis.Settings.Mtf.IAS_FftMtf(a.GetSettings());sett.MaximumFrequency=20;sett.SampleSize=Z.Analysis.SampleSizes.S_128x128
start=time.time();a.ApplyAndWaitForCompletion();res=a.GetResults();res.GetTextFile(str(ROOT/'analysis'/'seed_mtf.txt'))
print('time',time.time()-start,'series',res.NumberOfDataSeries)
for i in range(res.NumberOfDataSeries):
 d=res.GetDataSeries(i);x=np.array(list(d.XData.Data));y=np.array(list(d.YData.Data)).reshape(d.YData.Data.GetLength(0),-1)
 print(i,[(f, np.round([np.interp(f,x,y[:,j]) for j in range(2)],3).tolist()) for f in [5,10,20]])
print('asphere params',[(i,sys.LDE.GetSurfaceAt(10).GetCellAt(i).Header) for i in range(10,20)])
sys.SaveAs(str(ROOT/'models'/'seed_evaluated.zmx'))
a.Close();app.CloseApplication()



