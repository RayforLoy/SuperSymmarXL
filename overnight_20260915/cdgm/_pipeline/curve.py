from pathlib import Path
import argparse,atexit,hashlib
parser=argparse.ArgumentParser();parser.add_argument('--input',default='SuperSymmarXL_150_CDGM_f5p6.zmx');args=parser.parse_args()
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
close_on_exit=app.CloseApplication
atexit.register(close_on_exit)
import numpy as np,json
R = Path('D:\\_Camera\\LensRebuild\\SuperSymmarXL\\overnight_20260915\\cdgm');sys.LoadFile(str(R/args.input),False)
v=json.loads((R/'validated.json').read_text())
assert hashlib.sha256((R/args.input).read_bytes()).hexdigest()==v['official_file_sha256'][Path(args.input).name]
a=sys.Analyses.New_FftMtf();s=Z.Analysis.Settings.Mtf.IAS_FftMtf(a.GetSettings());s.MaximumFrequency=20;s.SampleSize=Z.Analysis.SampleSizes.S_512x512
s.Field.UseAllFields();s.Wavelength.UseAllWavelengths()
target=json.loads((R/'target_optimization.json').read_text())
heights=sorted(set([i/40 for i in range(41)]+target.get('heights',[])+sum(target.get('heights_by_aperture',{}).values(),[])))
batches=[]
inner=heights[1:-1]
for i in range(0,len(inner),10):batches.append([0]+inner[i:i+10]+[1])
values={fn:{} for fn in ['5.6','8','22']}
for bi,hs in enumerate(batches):
 while sys.SystemData.Fields.NumberOfFields>1:sys.SystemData.Fields.RemoveField(sys.SystemData.Fields.NumberOfFields)
 for h in hs[1:]:sys.SystemData.Fields.AddField(0,float(np.degrees(np.arctan(h*193/148.1))) if h<1 else 52.5,1)
 assert sys.SystemData.Fields.NumberOfFields==len(hs) and len(hs)<=12
 for fn in values:
  sys.SystemData.Aperture.ApertureValue=148.1/float(fn);a.ApplyAndWaitForCompletion();res=a.GetResults();assert res.NumberOfDataSeries==len(hs)
  for i,h in enumerate(hs):
   d=res.GetDataSeries(i);xx=np.array(list(d.XData.Data));yy=np.array(list(d.YData.Data)).reshape(d.YData.Data.GetLength(0),-1)
   values[fn][h]=[float(np.interp(f,xx,yy[:,j])) for f in [5,10,20] for j in [0,1]]
  print('CDGM curve batch',bi+1,fn,flush=True)
(R/'field_curves.json').write_text(json.dumps({'source_sha256':v['source_sha256'],'model_sha256':hashlib.sha256((R/args.input).read_bytes()).hexdigest(),'official_image_distance_mm':float(sys.LDE.GetSurfaceAt(12).Thickness),'heights':heights,'results':{fn:[values[fn][h] for h in heights] for fn in values},'sampling':512,'note':'Native FFT analysis in batches of at most 12 fields; each retains maximum 52.5 degrees. Dense field samples plus all reference knots. Common image plane and unchanged physical apertures; analysis batches are never saved as model field configuration.'},indent=2))
atexit.unregister(close_on_exit)
a.Close();app.CloseApplication()
