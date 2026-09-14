"""Native high-sampling audit and final export for R3; no fitted MTF surrogates."""
from pathlib import Path
import argparse,json,csv
import numpy as np

parser=argparse.ArgumentParser()
parser.add_argument('--input',default='search1_best.zmx')
args=parser.parse_args()
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
R=ROOT/'revision3'
sys.LoadFile(str(R/args.input),False)
sys.Tools.RemoveAllVariables()
sys.SystemData.Advanced.TurnOffThreading=False
sys.SystemData.RayAiming.RayAiming=Z.SystemData.RayAimingMethod.Real
target=json.loads((R/'target_optimization.json').read_text())
constraints=json.loads((ROOT/'revision2'/'drawing_constraints.json').read_text())
for i,r in constraints['clear_semidiameters_mm'].items():sys.LDE.GetSurfaceAt(int(i)).MechanicalSemiDiameter=r
a=sys.Analyses.New_FftMtf();s=Z.Analysis.Settings.Mtf.IAS_FftMtf(a.GetSettings());s.MaximumFrequency=20
out={};convergence={};samples={};saved=[];angles_by_aperture={}
def set_fields(hs):
 fields=sys.SystemData.Fields
 while fields.NumberOfFields>1:fields.RemoveField(fields.NumberOfFields)
 for h in hs[1:]:fields.AddField(0,float(np.degrees(np.arctan(h*193/148.1))) if h<1 else 52.5,1)
 if hs[-1]<1:fields.AddField(0,52.5,1)
 assert fields.NumberOfFields<=12
 assert fields.GetField(fields.NumberOfFields).Y==52.5

def run(fn,size,hs):
 sys.SystemData.Aperture.ApertureValue=148.1/float(fn)
 s.SampleSize=getattr(Z.Analysis.SampleSizes,f'S_{size}x{size}')
 vals={};interior=[h for h in hs if 0<h<1]
 for offset in range(0,max(1,len(interior)),10):
  batch=[0]+interior[offset:offset+10]+[1];set_fields(batch)
  a.ApplyAndWaitForCompletion();res=a.GetResults()
  assert res.NumberOfDataSeries==sys.SystemData.Fields.NumberOfFields
  res.GetTextFile(str(R/f'MTF_f{fn}_{size}_batch{offset//10+1}.txt'))
  for i,h in enumerate(batch):
   d=res.GetDataSeries(i);xx=np.array(list(d.XData.Data));yy=np.array(list(d.YData.Data)).reshape(d.YData.Data.GetLength(0),-1)
   vals[h]=[float(np.interp(f,xx,yy[:,j])) for f in [5,10,20] for j in [0,1]]
 return np.array([vals[h] for h in hs]),res

for fn in ['5.6','8','22']:
 hs=target.get('heights_by_aperture',{}).get(fn,target.get('heights',[])[:len(target['data'][fn])])
 low,_=run(fn,256,hs);size=1024 if fn=='5.6' else 512
 high,res=run(fn,size,hs);res.GetTextFile(str(R/f'MTF_f{fn}_{size}.txt'))
 out[fn]=high.tolist();samples[fn]=size;convergence[fn]=float(np.max(abs(high-low)))
 print('R3 native audit',fn,'max shortfall',float(np.max(np.array(target['data'][fn])-high)),'sampling delta',convergence[fn],flush=True)
 # All models contain the same full-field configuration and common image plane.
 set_fields([0,.2,.4,.6,.68,.8,1])
 title=sys.SystemData.TitleNotes
 title.Title='Super-Symmar XL 150 mm - R3 reverse candidate - full 105 deg'
 title.Author='Reverse engineering study'
 title.Notes='R3: audited manufacturer digitization; full 105 degree field at all apertures; fixed clear apertures; automatic stop; common image plane. See merged optical and manufacturing report for numerical acceptance, limitations, geometry and glass substitutes.'
 p=R/f'SuperSymmarXL_150_R3_f{fn.replace(".","p")}.zmx'
 sys.SaveAs(str(p));saved.append(p.name)
 angles_by_aperture[fn]=[sys.SystemData.Fields.GetField(i).Y for i in range(1,8)]

# Report the automatic stop at the primary f/5.6 aperture, rather than the
# last audit aperture f/22. Other optical surfaces and the image plane agree.
sys.LoadFile(str(R/saved[0]),False)
surfaces=[]
for i in range(1,13):
 ss=sys.LDE.GetSurfaceAt(i);surfaces.append({'surface':i,'radius_mm':ss.Radius,'thickness_mm':ss.Thickness,'glass':ss.Material,'clear_radius_mm':ss.SemiDiameter,'mechanical_radius_mm':ss.MechanicalSemiDiameter,'stop':bool(ss.IsStop)})
coef=[sys.LDE.GetSurfaceAt(10).GetCellAt(i).DoubleValue for i in range(13,20)]
if not any(coef[5:]):coef=coef[:5]
first={name:sys.MFE.GetOperandValue(getattr(Z.Editors.MFE.MeritOperandType,name),0,1,0,0,0,0,0,0) for name in ['EFFL','ENPP','EXPP','EXPD']}
summary={'results':out,'convergence_from_256':convergence,'sampling':samples,'surfaces':surfaces,'asphere_A4_to_A12':coef,'first_order':first,'field_type':str(sys.SystemData.Fields.GetFieldType()),'field_angles_deg':angles_by_aperture['5.6'],'field_angles_by_aperture':angles_by_aperture,'full_field_deg':105.,'stop_solve':str(sys.LDE.GetSurfaceAt(7).SemiDiameterCell.GetSolveData().Type),'files':saved,'target_file':'target_optimization.json','heights_by_aperture':target.get('heights_by_aperture',{}),'common_image_distance_mm':surfaces[-1]['thickness_mm'],'image_plane_policy':'One common image distance at all three apertures.','ray_aiming_method':str(sys.SystemData.RayAiming.RayAiming)}
summary['asphere_powers']=list(range(4,4+2*len(coef),2))
summary['source_candidate']=args.input
(R/'validated.json').write_text(json.dumps(summary,indent=2))
with (R/'prescription.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=surfaces[0]);w.writeheader();w.writerows(surfaces)
with (R/'comparison.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.writer(f);w.writerow(['f_number','reference_height_fraction','frequency_lp_mm','direction','reference','model','model_minus_reference','sampling'])
 for fn in out:
  hs=target.get('heights_by_aperture',{}).get(fn,target.get('heights',[])[:len(target['data'][fn])])
  for h,ref,model in zip(hs,target['data'][fn],out[fn]):
   for j,(rv,mv) in enumerate(zip(ref,model)):w.writerow([fn,h,[5,10,20][j//2],['T','S'][j%2],rv,mv,mv-rv,samples[fn]])
a.Close()
record=[]
for name in saved:
 sys.LoadFile(str(R/name),False)
 fields=[sys.SystemData.Fields.GetField(i).Y for i in range(1,8)]
 assert max(fields)==52.5 and str(sys.SystemData.Fields.GetFieldType())=='Angle'
 assert str(sys.LDE.GetSurfaceAt(7).SemiDiameterCell.GetSolveData().Type)=='Automatic'
 assert str(sys.SystemData.RayAiming.RayAiming)=='Real'
 for i,r in constraints['clear_semidiameters_mm'].items():assert sys.LDE.GetSurfaceAt(int(i)).SemiDiameter==r
 record.append({'file':name,'field_angles_deg':fields,'image_distance_mm':sys.LDE.GetSurfaceAt(12).Thickness,'entrance_pupil_mm':sys.SystemData.Aperture.ApertureValue})
assert len(set(d['image_distance_mm'] for d in record))==1
(R/'zmx_reopen_verification.json').write_text(json.dumps(record,indent=2))
app.CloseApplication()
