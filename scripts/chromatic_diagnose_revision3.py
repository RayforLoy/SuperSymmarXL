from pathlib import Path
import argparse,json,numpy as np
parser=argparse.ArgumentParser();parser.add_argument('--model',default='macro_parallel1_best.zmx');args=parser.parse_args()
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
R=ROOT/'revision3';sys.LoadFile(str(R/args.model),False)
out={'model':args.model,'image_distance_mm':sys.LDE.GetSurfaceAt(12).Thickness,'ray_aiming_method':str(sys.SystemData.RayAiming.RayAiming),'asphere_headers':{},'wavelengths':[]}
for i in range(12,20):
 cell=sys.LDE.GetSurfaceAt(10).GetCellAt(i);out['asphere_headers'][str(i)]={'header':str(cell.Header),'value':cell.DoubleValue}
for wave in range(1,7):
 matrix=np.eye(2);old=1
 for i in range(1,13):
  s=sys.LDE.GetSurfaceAt(i);n=sys.MFE.GetOperandValue(Z.Editors.MFE.MeritOperandType.INDX,i,wave,0,0,0,0,0,0)
  matrix=np.array([[1.,0.],[-(n-old)/s.Radius,1.]])@matrix
  if i<12:matrix=np.array([[1.,s.Thickness/n],[0.,1.]])@matrix
  old=n
 wl=sys.SystemData.Wavelengths.GetWavelength(wave)
 out['wavelengths'].append({'wave':wave,'wavelength_um':wl.Wavelength,'weight':wl.Weight,'efl_mm':-1/matrix[1,0],'bfl_mm':-matrix[0,0]/matrix[1,0]})
bfl=np.array([v['bfl_mm'] for v in out['wavelengths']]);weights=np.array([v['weight'] for v in out['wavelengths']]);weights/=weights.sum();mean=np.dot(bfl,weights)
out['weighted_bfl_mean_mm']=float(mean);out['weighted_bfl_std_mm']=float(np.sqrt(np.dot((bfl-mean)**2,weights)));out['primary_focus_difference_mm']=out['image_distance_mm']-bfl[0]
(R/(Path(args.model).stem+'_chromatic.json')).write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2),flush=True);app.CloseApplication()
