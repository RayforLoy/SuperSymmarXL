exec(open(__file__.replace('build_model.py','probe_zos.py')).read().split("print('system'")[0])
import numpy as np, json
sys.New(False)
sd=sys.SystemData
sd.MaterialCatalogs.AddCatalog('SCHOTT')
sd.Aperture.ApertureValue=148.1/5.6
waves=[(.546,24.6),(.644,18.6),(.588,22.1),(.480,12.4),(.436,15.2),(.405,7.1)]
w=sd.Wavelengths.GetWavelength(1); w.Wavelength,w.Weight=waves[0]
for lam,wt in waves[1:]:sd.Wavelengths.AddWavelength(lam,wt)
sd.Fields.SetFieldType(Z.SystemData.FieldType.ParaxialImageHeight)
for h in [19.3,38.6,57.9,77.2,96.5,115.8,135.1,154.4,173.7,193.0]:sd.Fields.AddField(0,h,1)
r=[201.077,33.369,37.3,60.315,36.588,43.742,0,98.97,-23.818,-42.216,-40.465,203.617]
t=[3.4,13,16.03,11.636,3.2,3.03,3.03,13.1,4.7,.99,5.3,135.9]
g=['KF9','','N-LAK33B','','N-LAK33B','','','N-SK5','F2','','K10','']
for _ in range(11):sys.LDE.InsertNewSurfaceAt(1)
for i in range(12):
 s=sys.LDE.GetSurfaceAt(i+1);s.Radius=r[i] if r[i] else float('inf');s.Thickness=t[i];s.Material=g[i];s.Comment='Patent surface '+str(i+1)
sys.LDE.GetSurfaceAt(7).IsStop=True
s=sys.LDE.GetSurfaceAt(10);s.ChangeType(s.GetSurfaceTypeSettings(Z.Editors.LDE.SurfaceType.EvenAspheric))
print('ray aim',dir(sd.RayAiming),flush=True)
print('EFL',sys.MFE.GetOperandValue(Z.Editors.MFE.MeritOperandType.EFFL,0,1,0,0,0,0,0,0),flush=True)
sys.SaveAs(str(ROOT/'models'/'patent_baseline.zmx'))
a=sys.Analyses.New_FftMtf();sett=a.GetSettings(); print('MTF settings',dir(sett),flush=True)
a.Close()
a=sys.Analyses.New_FftMtfvsField(); print('MTFfield settings',dir(a.GetSettings()),flush=True);a.Close()
app.CloseApplication()
