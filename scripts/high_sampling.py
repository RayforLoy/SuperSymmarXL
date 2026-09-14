from pathlib import Path
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
import json,numpy as np,time
sys.LoadFile(str(ROOT/'models'/'SuperSymmarXL_150_f5p6_reverse.zmx'),False)
a=sys.Analyses.New_FftMtf();s=Z.Analysis.Settings.Mtf.IAS_FftMtf(a.GetSettings());s.MaximumFrequency=20
out={}
for size in [1024,2048]:
 s.SampleSize=getattr(Z.Analysis.SampleSizes,'S_'+str(size)+'x'+str(size));start=time.time();a.ApplyAndWaitForCompletion();res=a.GetResults();res.GetTextFile(str(ROOT/'analysis'/('native_MTF_f5.6_'+str(size)+'.txt')))
 vals=[]
 for i in range(res.NumberOfDataSeries):
  d=res.GetDataSeries(i);xx=np.array(list(d.XData.Data));yy=np.array(list(d.YData.Data)).reshape(d.YData.Data.GetLength(0),-1);vals.append([float(np.interp(f,xx,yy[:,j])) for f in [5,10,20] for j in range(2)])
 out[str(size)]=vals;print('high sampling',size,'seconds',time.time()-start,flush=True)
(ROOT/'analysis'/'high_sampling_check.json').write_text(json.dumps(out,indent=2));a.Close();app.CloseApplication()
