"""Read-only final native prescription integrity check for all three apertures."""
from pathlib import Path
import json,hashlib,numpy as np
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
R=ROOT/'revision3';v=json.loads((R/'validated.json').read_text());records=[]
try:
 for name in v['files']:
  path=R/name;sys.LoadFile(str(path),False)
  coeff=[sys.LDE.GetSurfaceAt(10).GetCellAt(i).DoubleValue for i in range(13,20)]
  assert np.allclose(coeff,v['asphere_A4_to_A12'],rtol=1e-13,atol=0)
  assert sys.LDE.GetSurfaceAt(10).Conic==0
  assert max(sys.SystemData.Fields.GetField(i).Y for i in range(1,8))==52.5
  assert str(sys.SystemData.RayAiming.RayAiming)=='Real'
  for row in v['surfaces']:
   ss=sys.LDE.GetSurfaceAt(row['surface'])
   if np.isfinite(row['radius_mm']):assert abs(ss.Radius-row['radius_mm'])<1e-8
   assert abs(ss.Thickness-row['thickness_mm'])<1e-8
   assert ss.Material==row['glass']
   if row['surface']!=7:assert ss.SemiDiameter==row['clear_radius_mm']
  records.append({'file':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'asphere_A4_to_A16':coeff,'image_distance_mm':sys.LDE.GetSurfaceAt(12).Thickness,'internal_threading_disabled':bool(sys.SystemData.Advanced.TurnOffThreading)})
 (R/'final_integrity.json').write_text(json.dumps(records,indent=2))
 print('Verified all three native models: seven coefficients, radii, distances, glasses, apertures, Real aiming and full field.',flush=True)
finally:app.CloseApplication()
