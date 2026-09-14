"""Independent native 512 field batches, fixed source and common image plane."""
from pathlib import Path
import argparse,json,hashlib,os,shutil,multiprocessing as mp
from multiprocessing.util import Finalize
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
P=Path(__file__).resolve().parents[1];R=P/'revision4'

def initialize(model):
    global app,sys,Z,a,s
    ns={'__file__':str(P/'scripts/probe_zos.py')}
    exec((P/'scripts/probe_zos.py').read_text().split("print('system'")[0],ns)
    app,sys,Z=(ns[k] for k in ['app','sys','Z'])
    Finalize(None,app.CloseApplication,exitpriority=20)
    private=R/'curve_workers'/str(os.getpid());private.mkdir(parents=True,exist_ok=True)
    cp=private/'seed.zmx';shutil.copy2(model,cp);sys.LoadFile(str(cp),False)
    sys.SystemData.Advanced.TurnOffThreading=False
    sys.SystemData.RayAiming.RayAiming=Z.SystemData.RayAimingMethod.Real
    a=sys.Analyses.New_FftMtf();s=Z.Analysis.Settings.Mtf.IAS_FftMtf(a.GetSettings())
    s.MaximumFrequency=20;s.SampleSize=Z.Analysis.SampleSizes.S_512x512
    s.Field.UseAllFields();s.Wavelength.UseAllWavelengths()

def evaluate(hs):
    fields=sys.SystemData.Fields
    while fields.NumberOfFields>1:fields.RemoveField(fields.NumberOfFields)
    for h in hs[1:]:fields.AddField(0,float(np.degrees(np.arctan(h*193/148.1))) if h<1 else 52.5,1)
    assert fields.NumberOfFields==len(hs) and len(hs)<=12
    assert fields.GetField(len(hs)).Y==52.5
    result={}
    for fn in ['5.6','8','22']:
        sys.SystemData.Aperture.ApertureValue=148.1/float(fn)
        a.ApplyAndWaitForCompletion();res=a.GetResults()
        assert res.NumberOfDataSeries==len(hs)
        values=[]
        for i,h in enumerate(hs):
            d=res.GetDataSeries(i);xx=np.array(list(d.XData.Data))
            yy=np.array(list(d.YData.Data)).reshape(d.YData.Data.GetLength(0),-1)
            values.append([float(np.interp(f,xx,yy[:,j])) for f in [5,10,20] for j in [0,1]])
        assert np.all(np.isfinite(values)) and np.min(values)>=0 and np.max(values)<=1.00001
        result[fn]=values
    return hs,result,float(sys.LDE.GetSurfaceAt(12).Thickness)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--input',default='SuperSymmarXL_150_R4_f5p6.zmx');args=parser.parse_args()
    assert 1<=args.workers<=8
    model=R/args.input;v=json.loads((R/'validated.json').read_text())
    model_hash=hashlib.sha256(model.read_bytes()).hexdigest()
    assert model_hash==v['official_file_sha256'][model.name]
    target=json.loads((R/'target_optimization.json').read_text())
    heights=sorted(set([i/40 for i in range(41)]+sum(target['heights_by_aperture'].values(),[])))
    inner=heights[1:-1];batches=[[0]+inner[i:i+10]+[1] for i in range(0,len(inner),10)]
    values={fn:{} for fn in ['5.6','8','22']}
    with ProcessPoolExecutor(max_workers=args.workers,mp_context=mp.get_context('spawn'),initializer=initialize,initargs=(str(model),)) as pool:
        jobs=[pool.submit(evaluate,hs) for hs in batches]
        for k,job in enumerate(as_completed(jobs),1):
            hs,result,distance=job.result()
            assert distance==v['common_image_distance_mm']
            for fn in values:
                for h,row in zip(hs,result[fn]):values[fn][h]=row
            print('Native dense curve batch completed',k,'/',len(batches),flush=True)
    output={'source_sha256':v['source_sha256'],'model_sha256':model_hash,'official_image_distance_mm':v['common_image_distance_mm'],
            'heights':heights,'results':{fn:[values[fn][h] for h in heights] for fn in values},'sampling':512,
            'note':'Isolated native FFT512 batches; all retain maximum half field52.5deg, common image plane and unchanged apertures. Analysis fields never saved as models.'}
    (R/'field_curves.json').write_text(json.dumps(output,indent=2))

if __name__=='__main__':main()
