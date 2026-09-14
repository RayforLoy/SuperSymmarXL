from pathlib import Path
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
import numpy as np,json
sys.LoadFile(str(ROOT/'models'/'physical_constrained.zmx'),False)
sys.Tools.RemoveAllVariables()
cap={1:41,2:29,3:25.8,4:19.5,5:15,6:14.5,8:14.4,9:14.4,10:15.5,11:14,12:18.8}
for i,r in cap.items():
 s=sys.LDE.GetSurfaceAt(i);s.SemiDiameter=r
 ad=s.ApertureData.CreateApertureTypeSettings(Z.Editors.LDE.SurfaceApertureTypes.CircularAperture);ad._S_CircularAperture.MaximumRadius=r;s.ApertureData.ChangeApertureTypeSettings(ad)
stop=sys.LDE.GetSurfaceAt(7);stop.SemiDiameterCell.SetSolveData(stop.SemiDiameterCell.CreateSolveType(Z.Editors.SolveType.Automatic))
sd=sys.SystemData;sd.Fields.SetFieldType(Z.SystemData.FieldType.Angle)
heights=[0,.2,.4,.6,.68,.8,1]
for i,h in enumerate(heights):sd.Fields.GetField(i+1).Y=float(np.degrees(np.arctan(193*h/148.1)))
a=sys.Analyses.New_FftMtf();sett=Z.Analysis.Settings.Mtf.IAS_FftMtf(a.GetSettings());sett.MaximumFrequency=20;sett.SampleSize=Z.Analysis.SampleSizes.S_128x128
tar=json.loads((ROOT/'analysis'/'target_manual.json').read_text())['data'];out={}
for fn in ['5.6','8','22']:
 sd.Aperture.ApertureValue=148.1/float(fn);a.ApplyAndWaitForCompletion();res=a.GetResults();res.GetTextFile(str(ROOT/'revision2'/('physical_aperture_'+fn+'.txt')))
 yy=[]
 for i in range(res.NumberOfDataSeries):
  d=res.GetDataSeries(i);x=np.array(list(d.XData.Data));y=np.array(list(d.YData.Data)).reshape(d.YData.Data.GetLength(0),-1);yy.append([float(np.interp(f,x,y[:,j])) for f in [5,10,20] for j in [0,1]])
 out[fn]=yy;print(fn,'stop',stop.SemiDiameter,'series',len(yy),'rmse',np.sqrt(np.mean((np.array(yy[:len(tar[fn])])-tar[fn])**2)),np.round(yy[:2],3).tolist(),flush=True)
sd.Aperture.ApertureValue=148.1/5.6
sys.SaveAs(str(ROOT/'revision2'/'physical_aperture_seed.zmx'))
(ROOT/'revision2'/'physical_aperture_seed.json').write_text(json.dumps({'apertures':cap,'results':out},indent=2));a.Close();app.CloseApplication()
