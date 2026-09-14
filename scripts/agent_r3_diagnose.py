from pathlib import Path
import json
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'revision3'
target=json.loads((R/'target_optimization.json').read_text())
rows=[]
for fn in ['5.6','8','22']:
    hs=target['heights_by_aperture'][fn]
    for h,rr in zip(hs,target['data'][fn]):
        rows.extend((fn,h,frequency,direction,float(v)) for (frequency,direction),v in zip([(f,d) for f in [5,10,20] for d in ['T','S']],rr))
for name in (sys.argv[1:] or ['focused_seed_audit','broad_dense1_checkpoint','focused_dense1_checkpoint']):
    rec=json.loads((R/(name+'.json')).read_text())
    values=np.array(rec['results_flat'])
    if len(values)!=len(rows):
        print(name,'incompatible target lengths',len(values),len(rows));continue
    deficits=np.array([row[-1] for row in rows])-values
    print('\n',name,'maximum',max(deficits))
    print('first-order',rec.get('first_order'),'image-distance',rec.get('image_distance_mm'),'gaps',rec.get('geometry_gaps'))
    for index in np.argsort(deficits)[-20:][::-1]:
        fn,h,f,d,v=rows[index]
        print(f'{fn:4} h {h:.2f} {f:2}{d} ref {v:.3f} actual {values[index]:.3f} shortfall {deficits[index]:.4f}')
    print('Aperture summary')
    for fn in ['5.6','8','22']:
        ds=deficits[[i for i,row in enumerate(rows) if row[0]==fn]]
        print(fn,'max',np.max(ds),'rms',np.sqrt(np.mean(np.maximum(ds,0)**2)))
