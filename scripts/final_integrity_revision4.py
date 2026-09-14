"""Read-only final native prescription integrity check for all three apertures."""
from pathlib import Path
import json,hashlib,re,numpy as np
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
R=ROOT/'revision4';v=json.loads((R/'validated.json').read_text());records=[]
try:
 assert hashlib.sha256((R/v['source_candidate']).read_bytes()).hexdigest()==v['source_sha256']
 for name in v['files']:
  path=R/name;sys.LoadFile(str(path),False)
  assert hashlib.sha256(path.read_bytes()).hexdigest()==v['official_file_sha256'][name]
  raw=path.read_bytes()
  native_text=raw.decode('utf-16' if raw[:2] in [b'\xff\xfe',b'\xfe\xff'] else 'utf-8-sig')
  asphere_surfaces=[]
  for number,block in re.findall(r'^SURF\s+(\d+)\s*\n(.*?)(?=^SURF\s+\d+|\Z)',native_text,re.M|re.S):
   type_match=re.search(r'^\s*TYPE\s+(\S+)',block,re.M)
   if not type_match:continue
   if type_match.group(1)=='EVENASPH':
    asphere_surfaces.append(int(number))
    for parameter,value in re.findall(r'^\s*PARM\s+(\d+)\s+(\S+)',block,re.M):
     if int(parameter)==1 or int(parameter)>3:assert float(value)==0., 'Unexpected active higher-order coefficient'
   else:assert type_match.group(1)=='STANDARD', 'Unexpected alternate surface representation'
  assert asphere_surfaces==[10]
  coeff=[sys.LDE.GetSurfaceAt(10).GetCellAt(i).DoubleValue for i in range(13,20)]
  assert not any(coeff[2:]), 'A8 and higher must be zero'
  assert sys.LDE.GetSurfaceAt(10).GetCellAt(12).DoubleValue==0
  assert np.allclose(coeff[:2],v['asphere_A4_to_A6'],rtol=1e-13,atol=0)
  assert sys.LDE.GetSurfaceAt(10).Conic==0
  assert max(sys.SystemData.Fields.GetField(i).Y for i in range(1,8))==52.5
  assert str(sys.SystemData.RayAiming.RayAiming)=='Real'
  for row in v['surfaces']:
   ss=sys.LDE.GetSurfaceAt(row['surface'])
   assert ss.Conic==0. and row['conic']==0., 'All R4 conics must be zero'
   if np.isfinite(row['radius_mm']):assert abs(ss.Radius-row['radius_mm'])<1e-8
   assert abs(ss.Thickness-row['thickness_mm'])<1e-8
   assert ss.Material==row['glass']
   if row['surface']!=7:assert ss.SemiDiameter==row['clear_radius_mm']
  records.append({'file':name,'source_sha256':v['source_sha256'],'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'asphere_A4_to_A16':coeff,'image_distance_mm':sys.LDE.GetSurfaceAt(12).Thickness,'internal_threading_disabled':bool(sys.SystemData.Advanced.TurnOffThreading)})
 (R/'final_integrity.json').write_text(json.dumps(records,indent=2))
 print('Verified all three native models: A4/A6 only, zero higher coefficients, radii, distances, glasses, apertures, Real aiming and full field.',flush=True)
finally:app.CloseApplication()
