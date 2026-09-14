"""Export an agent checkpoint using one native instance, then close it."""
from pathlib import Path
import argparse,json
import numpy as np
import agent_r3_smooth_search as search

def main():
    p=argparse.ArgumentParser();p.add_argument('checkpoint',type=Path);p.add_argument('--size',type=int,default=256)
    a=p.parse_args();record=json.loads(a.checkpoint.read_text())
    higher=len(record['x'])==30
    search.OUT.mkdir(parents=True,exist_ok=True)
    search.initialize(record['seed'],a.size,record['target'],record.get('mode','smoothmax'),higher)
    try:
        output=a.checkpoint.with_name(a.checkpoint.name.replace('_checkpoint.json','_best.zmx'))
        _,r=search.evaluate(np.array(record['x'])[:-1],str(output))
        r.update(seed=record['seed'],target=record['target'],sampling=a.size,mode=record.get('mode','smoothmax'),file=str(output))
        output.with_suffix('.json').write_text(json.dumps(r,indent=2))
        print('EXPORTED',output,'max',r['max_shortfall'],'first',r['first_order'],'gap',r['geometry_gaps'][7],flush=True)
    finally:
        search.core.analysis.Close();search.core.app.CloseApplication()

if __name__=='__main__':main()
