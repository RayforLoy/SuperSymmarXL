from pathlib import Path
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
import numpy as np,json,csv,time
sys.LoadFile(str(ROOT/'models'/'SuperSymmarXL_150_f5p6_reverse.zmx'),False)
sys.Tools.RemoveAllVariables()
target=json.loads((ROOT/'analysis'/'target_manual.json').read_text())
a=sys.Analyses.New_FftMtf();sett=Z.Analysis.Settings.Mtf.IAS_FftMtf(a.GetSettings());sett.MaximumFrequency=40
results={};convergence={}
def get(fn,sampling):
 n=len(target['data'][str(fn)])
 while sys.SystemData.Fields.NumberOfFields>n:sys.SystemData.Fields.RemoveField(sys.SystemData.Fields.NumberOfFields)
 while sys.SystemData.Fields.NumberOfFields<n:
  idx=sys.SystemData.Fields.NumberOfFields;sys.SystemData.Fields.AddField(0,193*target['heights'][idx],1)
 sys.SystemData.Aperture.ApertureValue=148.1/fn;sett.SampleSize=sampling
 a.ApplyAndWaitForCompletion();res=a.GetResults();out=[]
 for i in range(len(target['data'][str(fn)])):
  d=res.GetDataSeries(i);xx=np.array(list(d.XData.Data));yy=np.array(list(d.YData.Data)).reshape(d.YData.Data.GetLength(0),-1)
  out.append([float(np.interp(f,xx,yy[:,j])) for f in [5,10,20] for j in range(2)])
 return np.array(out),res
for fn in [5.6,8,22]:
 y256,_=get(fn,Z.Analysis.SampleSizes.S_256x256)
 y512,res=get(fn,Z.Analysis.SampleSizes.S_512x512)
 res.GetTextFile(str(ROOT/'analysis'/('native_MTF_f'+str(fn)+'_512.txt')))
 results[str(fn)]=y512.tolist();convergence[str(fn)]=float(np.max(np.abs(y512-y256)))
 sys.SaveAs(str(ROOT/'models'/('SuperSymmarXL_150_f'+str(fn).replace('.','p')+'_reverse.zmx')))
 print('verified',fn,'convergence',convergence[str(fn)],flush=True)
# Prescription and first order quantities at the primary wavelength.
sys.SystemData.Aperture.ApertureValue=148.1/5.6
surfaces=[]
for i in range(1,13):
 s=sys.LDE.GetSurfaceAt(i)
 surfaces.append({'surface':i,'radius_mm':s.Radius,'thickness_mm':s.Thickness,'glass':s.Material,'semi_diameter_mm':s.SemiDiameter,'stop':bool(s.IsStop)})
asph=[sys.LDE.GetSurfaceAt(10).GetCellAt(i).DoubleValue for i in [13,14,15,16,17]]
first={}
for name in ['EFFL','ENPP','EXPP','EXPD']:
 first[name]=sys.MFE.GetOperandValue(getattr(Z.Editors.MFE.MeritOperandType,name),0,1,0,0,0,0,0,0)
# Independent paraxial matrix validation and wavelength focal shifts.
for wave in [1,2,3,4,5,6]:
 M=np.eye(2);prev=1
 for d in surfaces:
  i=d['surface'];n=sys.MFE.GetOperandValue(Z.Editors.MFE.MeritOperandType.INDX,i,wave,0,0,0,0,0,0)
  M=np.array([[1,0],[-(n-prev)/d['radius_mm'],1]])@M
  if i<12:M=np.array([[1,d['thickness_mm']/n],[0,1]])@M
  prev=n
 first['wave_'+str(wave)]={'efl':float(-1/M[1,0]),'bfl':float(-M[0,0]/M[1,0])}
# Real chief-ray distortion (relative to paraxial image-height coordinate).
dist=[]
for h in target['heights']:
 y=sys.MFE.GetOperandValue(Z.Editors.MFE.MeritOperandType.REAY,13,1,0,h,0,0,0,0)
 dist.append({'height_mm':h*193,'chief_y_mm':y,'distortion_pct':100*(y/(h*193)-1) if h else 0})
# One-at-a-time sensitivity; no compensation, at f/22. Not a Monte Carlo yield estimate.
sett.SampleSize=Z.Analysis.SampleSizes.S_256x256
base,_=get(22,Z.Analysis.SampleSizes.S_256x256)
sens=[]
pert=[('image focus',12,'Thickness',.05),('front radius',1,'Radius',surfaces[0]['radius_mm']*.001),('L2 center thickness',3,'Thickness',.02),('L3-to-stop air gap',6,'Thickness',.02),('cemented group thickness',8,'Thickness',.02),('rear air gap',10,'Thickness',.02)]
for name,i,prop,delta in pert:
 s=sys.LDE.GetSurfaceAt(i);orig=getattr(s,prop)
 for sign in [-1,1]:
  setattr(s,prop,orig+sign*delta);val,_=get(22,Z.Analysis.SampleSizes.S_256x256)
  sens.append({'parameter':name,'surface':i,'delta_mm':sign*delta,'mtf_max_change':float(np.max(np.abs(val-base))),'mtf_rms_change':float(np.sqrt(np.mean((val-base)**2)))})
 setattr(s,prop,orig)
summary={'results':results,'convergence_256_512':convergence,'surfaces':surfaces,'asphere_A4_A6_A8_A10_A12':asph,'first_order':first,'distortion':dist,'sensitivity':sens}
(ROOT/'analysis'/'validated_results.json').write_text(json.dumps(summary,indent=2))
with (ROOT/'analysis'/'prescription.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=surfaces[0].keys());w.writeheader();w.writerows(surfaces)
with (ROOT/'analysis'/'mtf_comparison.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['f_number','relative_height','frequency_lp_mm','direction','reference_manual','model_512','error'])
 for fn in results:
  for i,row in enumerate(results[fn]):
   for j,val in enumerate(row):w.writerow([fn,target['heights'][i],[5,10,20][j//2],['T','S'][j%2],target['data'][fn][i][j],val,val-target['data'][fn][i][j]])
sys.SystemData.Aperture.ApertureValue=148.1/5.6
while sys.SystemData.Fields.NumberOfFields>5:sys.SystemData.Fields.RemoveField(sys.SystemData.Fields.NumberOfFields)
sys.SaveAs(str(ROOT/'models'/'SuperSymmarXL_150_f5p6_reverse.zmx'))
a.Close();app.CloseApplication()
