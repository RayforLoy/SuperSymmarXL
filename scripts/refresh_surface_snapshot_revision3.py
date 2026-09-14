"""Refresh primary-aperture prescription metadata; no optical model changes."""
from pathlib import Path
import json,csv
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
R=ROOT/'revision3'
try:
 sys.LoadFile(str(R/'SuperSymmarXL_150_R3_f5p6.zmx'),False)
 v=json.loads((R/'validated.json').read_text())
 for item in v['surfaces']:
  s=sys.LDE.GetSurfaceAt(item['surface'])
  assert abs(s.Thickness-item['thickness_mm'])<1e-8
  item['clear_radius_mm']=s.SemiDiameter;item['mechanical_radius_mm']=s.MechanicalSemiDiameter
 v['prescription_snapshot_aperture']='5.6'
 (R/'validated.json').write_text(json.dumps(v,indent=2))
 with (R/'prescription.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=v['surfaces'][0]);w.writeheader();w.writerows(v['surfaces'])
 print('Primary automatic stop radius',v['surfaces'][6]['clear_radius_mm'],flush=True)
finally:app.CloseApplication()
