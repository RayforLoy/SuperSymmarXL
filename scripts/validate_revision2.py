from pathlib import Path
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
import numpy as np,json,csv,time
R=ROOT/'revision2';sys.LoadFile(str(R/'SuperSymmarXL_150_R2_refined.zmx'),False);sys.Tools.RemoveAllVariables()
constraints=json.loads((R/'drawing_constraints.json').read_text());caps={int(i):r for i,r in constraints['clear_semidiameters_mm'].items()}
for i,r in caps.items():sys.LDE.GetSurfaceAt(i).MechanicalSemiDiameter=r
sys.SystemData.Fields.GetField(sys.SystemData.Fields.NumberOfFields).Y=52.5
sys.LDE.GetSurfaceAt(1).Comment='R2 full 105 degree field; fixed drawing-derived clear apertures; see R2 report'
target=json.loads((ROOT/'analysis/target_manual.json').read_text())
a=sys.Analyses.New_FftMtf();s=Z.Analysis.Settings.Mtf.IAS_FftMtf(a.GetSettings());s.MaximumFrequency=20
out={};convergence={};samples={};files=[]
def run(fn,size):
 sys.SystemData.Aperture.ApertureValue=148.1/float(fn);s.SampleSize=getattr(Z.Analysis.SampleSizes,'S_'+str(size)+'x'+str(size));a.ApplyAndWaitForCompletion();res=a.GetResults();vals=[]
 for i in range(res.NumberOfDataSeries):
  d=res.GetDataSeries(i);xx=np.array(list(d.XData.Data));yy=np.array(list(d.YData.Data)).reshape(d.YData.Data.GetLength(0),-1);vals.append([float(np.interp(f,xx,yy[:,j])) for f in [5,10,20] for j in [0,1]])
 return np.array(vals),res
for fn in ['5.6','8','22']:
 low,_=run(fn,256);size=1024 if fn=='5.6' else 512;high,res=run(fn,size)
 path=R/('MTF_f'+fn+'_'+str(size)+'.txt');res.GetTextFile(str(path));samples[fn]=size;out[fn]=high.tolist();convergence[fn]=float(np.max(abs(high-low)))
 dest=R/('SuperSymmarXL_150_R2_f'+fn.replace('.','p')+'.zmx');sys.SaveAs(str(dest));files.append(str(dest.name));print('verified R2',fn,'sampling',size,'delta',convergence[fn],flush=True)
# Preserve the full field at all apertures. No field deletion during validation or saving.
sys.SystemData.Aperture.ApertureValue=148.1/5.6
surfaces=[]
for i in range(1,13):
 ss=sys.LDE.GetSurfaceAt(i);surfaces.append({'surface':i,'radius_mm':ss.Radius,'thickness_mm':ss.Thickness,'glass':ss.Material,'clear_radius_mm':ss.SemiDiameter,'mechanical_radius_mm':ss.MechanicalSemiDiameter,'stop':bool(ss.IsStop)})
coef=[sys.LDE.GetSurfaceAt(10).GetCellAt(i).DoubleValue for i in range(13,18)]
first={name:sys.MFE.GetOperandValue(getattr(Z.Editors.MFE.MeritOperandType,name),0,1,0,0,0,0,0,0) for name in ['EFFL','ENPP','EXPP','EXPD']}
angles=[sys.SystemData.Fields.GetField(i).Y for i in range(1,sys.SystemData.Fields.NumberOfFields+1)]
summary={'results':out,'convergence_from_256':convergence,'sampling':samples,'surfaces':surfaces,'asphere_A4_to_A12':coef,'first_order':first,'field_type':str(sys.SystemData.Fields.GetFieldType()),'field_angles_deg':angles,'full_field_deg':2*max(angles),'stop_solve':str(sys.LDE.GetSurfaceAt(7).SemiDiameterCell.GetSolveData().Type),'files':files}
(R/'validated.json').write_text(json.dumps(summary,indent=2))
with (R/'prescription.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=surfaces[0]);w.writeheader();w.writerows(surfaces)
with (R/'comparison.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['f_number','reference_height_fraction','frequency_lp_mm','direction','reference','model','model_minus_reference','sampling'])
 for fn in out:
  for i,ref in enumerate(target['data'][fn]):
   for j,rv in enumerate(ref):mv=out[fn][i][j];w.writerow([fn,target['heights'][i],[5,10,20][j//2],['T','S'][j%2],rv,mv,mv-rv,samples[fn]])
sys.SaveAs(str(R/'SuperSymmarXL_150_R2_f5p6.zmx'));a.Close()
app.CloseApplication()
