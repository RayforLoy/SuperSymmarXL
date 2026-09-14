"""R2 recomputation against R3 audited targets and the factory focus rule."""
import json,numpy as np
import optimize_revision3 as c
c.initialize(str(c.ROOT/'revision2/SuperSymmarXL_150_R2_f5p6.zmx'),256,str(c.R/'target_optimization.json'),True,True)
try:
 _,v=c.evaluate(np.zeros(28),str(c.R/'R2_same_condition_baseline.zmx'))
 v['sampling']=256;v['target_file']='target_optimization.json';v['source']='revision2/SuperSymmarXL_150_R2_f5p6.zmx'
 v['per_aperture']={};offset=0
 for fn in ['5.6','8','22']:
  ref=np.array(c.target['data'][fn]);n=ref.size;yy=np.array(v['results_flat'][offset:offset+n]).reshape(ref.shape);offset+=n
  v['per_aperture'][fn]={'max_shortfall':float(np.maximum(ref-yy,0).max()),'deficit_rms':float(np.sqrt(np.mean(np.maximum(ref-yy,0)**2))),'at_or_above_reference':int((yy>=ref).sum()),'points':n}
 (c.R/'R2_same_condition_baseline.json').write_text(json.dumps(v,indent=2))
 print(v['per_aperture'],flush=True)
finally:c.app.CloseApplication()
