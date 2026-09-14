from pathlib import Path
import json
cp=json.loads(Path('SuperSymmarXL/analysis/fit_round1.json').read_text())
exec(Path('SuperSymmarXL/scripts/fit_round2.py').read_text().split('count=0;')[0])
apply(cp['x'])
for i,r in {1:45,2:32,3:31,4:29,5:16,6:16,8:16,9:15,10:16,11:17,12:20}.items():
 s=sys.LDE.GetSurfaceAt(i);ad=s.ApertureData.CreateApertureTypeSettings(Z.Editors.LDE.SurfaceApertureTypes.CircularAperture)
 print(i,dir(ad._S_CircularAperture) if i==1 else '',flush=True)
 ad._S_CircularAperture.MaximumRadius=r;s.ApertureData.ChangeApertureTypeSettings(ad)
for fn in target:print(fn,np.round(calc(fn),3),flush=True)
sys.SaveAs(str(ROOT/'models'/'aperture_trial.zmx'))
a.Close();app.CloseApplication()
