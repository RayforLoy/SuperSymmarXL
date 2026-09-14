from pathlib import Path
exec(Path(__file__).with_name('fit_physical.py').read_text().split('count=0;')[0])
sys.LoadFile(str(ROOT/'models'/'SuperSymmarXL_150_f5p6_reverse.zmx'),False)
a=sys.Analyses.New_FftMtf();sett=Z.Analysis.Settings.Mtf.IAS_FftMtf(a.GetSettings());sett.MaximumFrequency=20;sett.SampleSize=Z.Analysis.SampleSizes.S_128x128
for yy in [154.4,193]:sys.SystemData.Fields.AddField(0,yy,1)
for i in [5,6]:print('axial marginal at',i,sys.MFE.GetOperandValue(Z.Editors.MFE.MeritOperandType.REAY,i,1,0,0,0,1,0,0),flush=True)
for rad in [14.9,15.2,15.5,16]:
 for i in [5,6]:
  ss=sys.LDE.GetSurfaceAt(i);ad=ss.ApertureData.CreateApertureTypeSettings(Z.Editors.LDE.SurfaceApertureTypes.CircularAperture);ad._S_CircularAperture.MaximumRadius=rad;ss.ApertureData.ChangeApertureTypeSettings(ad)
 yy=calc('5.6');print('L3 radius',rad,'rmse',np.sqrt(np.mean((yy-target['5.6'])**2)),np.round(yy[:2],3).tolist(),flush=True)
a.Close();app.CloseApplication()
