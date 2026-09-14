"""Read-only candidate evidence summarizer; generates JSON and CSV, no ZOS."""
from pathlib import Path
import json,csv
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'revision3';OUT=R/'agent_search'
target=json.loads((R/'target_optimization.json').read_text())
fnames=['5.6','8','22']
references={fn:np.array(target['data'][fn]) for fn in fnames}

def summarize(label,path,zmx=None,formal=False):
    data=json.loads(path.read_text())
    if formal:values={fn:np.array(data['results'][fn]) for fn in fnames}
    else:
        values={};offset=0;flat=np.array(data['results_flat'])
        for fn in fnames:
            count=references[fn].size
            values[fn]=flat[offset:offset+count].reshape(references[fn].shape);offset+=count
        assert offset==len(flat)
    result={'name':label,'evidence_file':str(path),'native_zmx':str(zmx) if zmx else None,
            'sampling':data.get('sampling'),'MTF_direction_columns':['5T','5S','10T','10S','20T','20S'],
            'per_aperture':{},'common_image_distance_mm':data.get('common_image_distance_mm',data.get('image_distance_mm'))}
    deltas=[]
    for fn in fnames:
        delta=values[fn]-references[fn];deltas.extend(delta.ravel())
        result['per_aperture'][fn]={'maximum_shortfall':float(max(0,-np.min(delta))),
                                    'deficit_rms':float(np.sqrt(np.mean(np.maximum(-delta,0)**2))),
                                    'signed_margin_rmse':float(np.sqrt(np.mean(delta**2))),
                                    'at_or_above_reference_count':int(np.sum(delta>=0)),
                                    'total_reference_samples':int(delta.size)}
    delta=np.array(deltas)
    result.update(maximum_shortfall=float(max(0,-delta.min())),deficit_rms=float(np.sqrt(np.mean(np.maximum(-delta,0)**2))),
                  at_or_above_reference_count=int(np.sum(delta>=0)),total_reference_samples=int(delta.size),
                  every_sample_at_or_above_reference=bool(np.all(delta>=0)))
    return result

results=[]
macro_snapshot=OUT/'macro_high_sampling_snapshot.json'
if macro_snapshot.exists():
    results.append(summarize('macro_parallel1 formal high-sampling',macro_snapshot,R/'macro_parallel1_best.zmx',True))
elif (OUT/'macro_high_sampling_summary.json').exists():
    results.append(json.loads((OUT/'macro_high_sampling_summary.json').read_text()))
latest=json.loads((R/'validated.json').read_text())
if not macro_snapshot.exists() or latest.get('source_candidate')!='macro_parallel1_best.zmx':
    results.append(summarize('formal high-sampling '+latest.get('source_candidate','unknown'),R/'validated.json',R/latest.get('source_candidate','unknown'),True))
for name in ['smooth_central1','higher7_asphereonly1','bend7_1']:
    path=OUT/(name+'_result.json')
    if not path.exists():path=OUT/(name+'_checkpoint.json')
    if not path.exists():continue
    results.append(summarize(name,path,OUT/(name+'_best.zmx')))
payload={'note':'Native FFT evidence at the stated sampling; each uses the published f/5.6 axis-20 best focus retained for all apertures and angle atan(193*h/148.1), with explicit max52.5 degrees. Sampling differs between candidates; numbers are not interchangeable formal acceptance. All>= means only these independently digitized 186 samples, not mathematical certification of the continuous curves.','candidates':results}
(OUT/'candidate_comparison.json').write_text(json.dumps(payload,indent=2))
with (OUT/'candidate_comparison.csv').open('w',newline='',encoding='utf-8-sig') as f:
    writer=csv.writer(f);writer.writerow(['candidate','sampling','max_shortfall','deficit_rms','at_or_above_count','total','f5p6_max','f8_max','f22_max','all_at_or_above'])
    for d in results:
        writer.writerow([d['name'],str(d['sampling']),d['maximum_shortfall'],d['deficit_rms'],d['at_or_above_reference_count'],d['total_reference_samples'],*[d['per_aperture'][fn]['maximum_shortfall'] for fn in fnames],d['every_sample_at_or_above_reference']])
print(json.dumps(payload,indent=2))
