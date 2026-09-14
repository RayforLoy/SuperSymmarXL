from pathlib import Path
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
import numpy as np,json
R=ROOT/'revision2';sys.LoadFile(str(R/'SuperSymmarXL_150_R2_f5p6.zmx'),False)
a=sys.Analyses.New_FftMtf();s=Z.Analysis.Settings.Mtf.IAS_FftMtf(a.GetSettings());s.MaximumFrequency=20;s.SampleSize=Z.Analysis.SampleSizes.S_512x512
batches=[[0]+[i/20 for i in range(1,11)]+[1],[0]+[i/20 for i in range(11,20)]+[1]]
values={fn:{} for fn in ['5.6','8','22']}
for bi,hs in enumerate(batches):
 while sys.SystemData.Fields.NumberOfFields>1:sys.SystemData.Fields.RemoveField(sys.SystemData.Fields.NumberOfFields)
 for h in hs[1:]:sys.SystemData.Fields.AddField(0,float(np.degrees(np.arctan(h*193/148.1))) if h<1 else 52.5,1)
 assert sys.SystemData.Fields.NumberOfFields==len(hs),(bi,sys.SystemData.Fields.NumberOfFields)
 assert sys.SystemData.Fields.GetField(len(hs)).Y==52.5
 for fn in values:
  sys.SystemData.Aperture.ApertureValue=148.1/float(fn);a.ApplyAndWaitForCompletion();res=a.GetResults();assert res.NumberOfDataSeries==len(hs)
  for i,h in enumerate(hs):
   d=res.GetDataSeries(i);xx=np.array(list(d.XData.Data));yy=np.array(list(d.YData.Data)).reshape(d.YData.Data.GetLength(0),-1);values[fn][h]=[float(np.interp(f,xx,yy[:,j])) for f in [5,10,20] for j in [0,1]]
  print('curve batch',bi+1,fn,flush=True)
heights=sorted(values['5.6']);assert len(heights)==21 and heights[-1]==1
(R/'field_curves.json').write_text(json.dumps({'heights':heights,'results':{fn:[values[fn][h] for h in heights] for fn in values},'sampling':512,'note':'Two batches because this OpticStudio installation permits 12 field entries. Each batch retains the full 52.5-degree semi-field. No model fields are saved or truncated.'},indent=2))
a.Close();app.CloseApplication()
