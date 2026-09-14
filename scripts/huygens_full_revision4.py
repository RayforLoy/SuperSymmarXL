"""Isolated native fixed-window diffraction audit and optional focus scan."""
from pathlib import Path
import argparse,json,math,os,shutil,time,hashlib
import numpy as np
from concurrent.futures import ProcessPoolExecutor,as_completed
import multiprocessing as mp
from multiprocessing.util import Finalize
P=Path(__file__).resolve().parents[1];R=P/'revision4'
def initialize(seed,pupil,image,delta,name):
 global app,sys,Z,a,s,base_focus,OUT
 ns={'__file__':str(P/'scripts/probe_zos.py')}
 exec((P/'scripts/probe_zos.py').read_text().split("print('system'")[0],ns)
 app,sys,Z=(ns[k] for k in ['app','sys','Z'])
 OUT=R/name;OUT.mkdir(exist_ok=True)
 private=OUT/str(os.getpid());private.mkdir(exist_ok=True)
 cp=private/'seed.zmx';shutil.copy2(seed,cp);sys.LoadFile(str(cp),False)
 sys.Tools.RemoveAllVariables();sys.SystemData.Advanced.TurnOffThreading=False
 Finalize(None,app.CloseApplication,exitpriority=20)
 sys.SystemData.RayAiming.RayAiming=Z.SystemData.RayAimingMethod.Real
 base_focus=sys.LDE.GetSurfaceAt(12).Thickness
 a=sys.Analyses.New_HuygensMtf();s=Z.Analysis.Settings.Mtf.IAS_HuygensMtf(a.GetSettings())
 s.MaximumFrequency=20;s.PupilSampleSize=getattr(Z.Analysis.SampleSizes,f'S_{pupil}x{pupil}');s.ImageSampleSize=getattr(Z.Analysis.SampleSizes,f'S_{image}x{image}')
 s.ImageDelta=delta;s.UsePolarization=False;s.Wavelength.UseAllWavelengths()
def evaluate(case):
 fn,h,offset=case
 sys.SystemData.Aperture.ApertureValue=148.1/float(fn)
 sys.LDE.GetSurfaceAt(12).Thickness=base_focus+offset
 fields=sys.SystemData.Fields
 while fields.NumberOfFields>1:fields.RemoveField(fields.NumberOfFields)
 if h not in [0,1]:fields.AddField(0,float(math.degrees(math.atan(193*h/148.1))),1)
 fields.AddField(0,52.5,1)
 s.Field.SetFieldNumber(1 if h==0 else 2)
 a.ApplyAndWaitForCompletion();res=a.GetResults()
 tag=f'f{fn}_h{h}_offset{offset}'.replace('.','p')
 raw=OUT/(tag+'.txt');res.GetTextFile(str(raw))
 assert res.NumberOfDataSeries==1,'No native Huygens data'
 d=res.GetDataSeries(0);xx=np.array(list(d.XData.Data));yy=np.array(list(d.YData.Data)).reshape(d.YData.Data.GetLength(0),-1)
 assert len(xx)>1 and xx[-1]>=20
 vals=[float(np.interp(f,xx,yy[:,j])) for f in [5,10,20] for j in [0,1]]
 assert np.all(np.isfinite(vals)) and min(vals)>=0 and max(vals)<=1.00001
 return {'aperture':fn,'height':h,'image_distance_offset_mm':offset,'official_image_distance_mm':float(base_focus),'actual_image_distance_mm':float(sys.LDE.GetSurfaceAt(12).Thickness),'values_5T_5S_10T_10S_20T_20S':vals,'raw_text':str(raw.relative_to(R)),'frequency_grid_min_step':float(np.min(np.diff(xx)))}
def main():
 p=argparse.ArgumentParser();p.add_argument('--seed',default=str(R/'SuperSymmarXL_150_R4_f5p6.zmx'));p.add_argument('--name',default='huygens_full_fixed_window');p.add_argument('--workers',type=int,default=6);p.add_argument('--pupil',type=int,default=128);p.add_argument('--image',type=int,default=512);p.add_argument('--delta',type=float,default=1);p.add_argument('--focus-scan',action='store_true');p.add_argument('--offset',type=float,default=0);p.add_argument('--cases',default=None);args=p.parse_args()
 assert 1<=args.workers<=8
 target=json.loads((R/'target_optimization.json').read_text());cases=[(fn,float(h),args.offset) for fn in ['5.6','8','22'] for h in target['heights_by_aperture'][fn]]
 if args.cases:cases=[(fn,float(h),args.offset) for group in args.cases.split(';') for fn,heights in [group.split(':')] for h in heights.split(',')]
 if args.focus_scan:cases+= [('5.6',0.,float(z)) for z in [-.15,-.10,-.05,.05,.10,.15]]
 result={'model':args.seed,'pupil_sampling':args.pupil,'image_sampling':args.image,'image_delta_um':args.delta,'target_file':'target_optimization.json','cases':[],'failures':[],'completed':False};start=time.time()
 result['source_sha256']=hashlib.sha256(Path(args.seed).read_bytes()).hexdigest()
 previous=R/(args.name+'.json')
 if previous.exists():
  old=json.loads(previous.read_text())
  assert all(old[k]==result[k] for k in ['model','pupil_sampling','image_sampling','image_delta_um'])
  result['cases']=old['cases'];result['resumed_from_completed_cases']=len(old['cases'])
 completed_keys={(x['aperture'],x['height'],x['image_distance_offset_mm']) for x in result['cases']}
 cases=[c for c in cases if c not in completed_keys]
 with ProcessPoolExecutor(max_workers=args.workers,mp_context=mp.get_context('spawn'),initializer=initialize,initargs=(args.seed,args.pupil,args.image,args.delta,args.name)) as pool:
  jobs={pool.submit(evaluate,c):c for c in cases}
  for job in as_completed(jobs):
   try:result['cases'].append(job.result())
   except Exception as e:result['failures'].append({'case':jobs[job],'error':repr(e)})
   result['seconds']=time.time()-start
   (R/(args.name+'.json')).write_text(json.dumps(result,indent=2))
   if len(result['cases'])%6==0:print('Huygens cases completed',len(result['cases']),'/',len(cases),'seconds',round(result['seconds']),flush=True)
 result['completed']=True;result['cases'].sort(key=lambda x:(float(x['aperture']),x['height'],x['image_distance_offset_mm']))
 if result['cases']:
  official={x['official_image_distance_mm'] for x in result['cases']}
  assert len(official)==1
  result['official_image_distance_mm']=official.pop()
 (R/(args.name+'.json')).write_text(json.dumps(result,indent=2))
 print('Completed Huygens protocol',len(result['cases']),'failures',result['failures'],flush=True)
if __name__=='__main__':main()
