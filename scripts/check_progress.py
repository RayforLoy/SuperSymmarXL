from pathlib import Path
import json
cp=json.loads(Path('SuperSymmarXL/analysis/fit_checkpoint.json').read_text())
exec(Path('SuperSymmarXL/scripts/fit_mtf.py').read_text().split('count=0;')[0])
apply(cp['x'])
for fn in target:print(fn,np.round(calc(fn),3),flush=True)
a.Close();app.CloseApplication()
