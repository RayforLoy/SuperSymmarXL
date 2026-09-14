from pathlib import Path
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
import json,numpy as np
allout={}
for fn,limit in [(5.6,.68),(8,.78),(22,1)]:
 sys.LoadFile(str(ROOT/'models'/'SuperSymmarXL_150_f5p6_reverse.zmx'),False)
 sys.SystemData.Aperture.ApertureValue=148.1/fn
 while sys.SystemData.Fields.NumberOfFields>1:sys.SystemData.Fields.RemoveField(sys.SystemData.Fields.NumberOfFields)
 sys.SystemData.Fields.AddField(0,193*limit,1)
 a=sys.Analyses.New_FftMtfvsField();s=Z.Analysis.Settings.Mtf.IAS_FftMtfvsField(a.GetSettings())
 s.SampleSize=Z.Analysis.SampleSizes.S_512x512;s.Freq_1=5;s.Freq_2=10;s.Freq_3=20;s.Freq_4=0;s.Freq_5=0;s.Freq_6=0;s.FieldDensity=21;s.ScanType=Z.Analysis.Settings.ScanTypes.Plus_Y;s.RemoveVignetting=False
 a.ApplyAndWaitForCompletion();res=a.GetResults();res.GetTextFile(str(ROOT/'analysis'/('native_MTF_vs_field_f'+str(fn)+'.txt')))
 arr=[]
 for i in range(res.NumberOfDataSeries):
  d=res.GetDataSeries(i);arr.append({'description':str(d.Description),'x':list(d.XData.Data),'y':np.array(list(d.YData.Data)).reshape(d.YData.Data.GetLength(0),-1).tolist()})
 allout[str(fn)]=arr;print('dense',fn,'series',len(arr),'samples',[len(d['x']) for d in arr],flush=True);a.Close()
(ROOT/'analysis'/'dense_mtf.json').write_text(json.dumps(allout,indent=2));app.CloseApplication()
