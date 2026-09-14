from pathlib import Path
import json,numpy as np,csv
P=Path(__file__).resolve().parents[1]
v=json.loads((P/'analysis/validated_results.json').read_text());h=json.loads((P/'analysis/high_sampling_check.json').read_text());t=json.loads((P/'analysis/target_manual.json').read_text())
v['results_512']=v.get('results_512',v['results'].copy());v['results']['5.6']=h['2048'];v['verified_sampling']={'5.6':2048,'8':512,'22':512}
v['convergence_1024_2048_f5p6']=float(np.max(np.abs(np.array(h['1024'])-h['2048'])))
v['convergence_512_2048_f5p6']=float(np.max(np.abs(np.array(v['results_512']['5.6'])-h['2048'])))
(P/'analysis/validated_results.json').write_text(json.dumps(v,indent=2))
with (P/'analysis/mtf_comparison.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['f_number','relative_height','frequency_lp_mm','direction','reference_manual','model','sampling','error'])
 for fn in v['results']:
  for i,row in enumerate(v['results'][fn]):
   for j,val in enumerate(row):w.writerow([fn,t['heights'][i],[5,10,20][j//2],['T','S'][j%2],t['data'][fn][i][j],val,v['verified_sampling'][fn],val-t['data'][fn][i][j]])
print('maximum delta 1024 to 2048',v['convergence_1024_2048_f5p6'])
print('maximum delta 512 to 2048',v['convergence_512_2048_f5p6'])
