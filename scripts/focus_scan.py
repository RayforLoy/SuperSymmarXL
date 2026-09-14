from pathlib import Path
import json
exec(Path('SuperSymmarXL/scripts/fit_round2.py').read_text().split('count=0;')[0])
x=np.array(json.loads((ROOT/'analysis'/'fit_round2.json').read_text())['x'])
for delta in np.linspace(-.8,.8,9):
 y=x.copy();y[3]+=delta;apply(y);v=calc(5.6);print(round(delta,2),np.round(v[0],3).tolist(),np.round(v[1],3).tolist(),flush=True)
a.Close();app.CloseApplication()
