"""Preserve audited knots and include the published f/8 endpoint in acceptance."""
from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]/'revision3'
target=json.loads((R/'target_dense_audited.json').read_text())
target['plot_only_additional_points']={}
target['note']+=' Dense independently re-read reference including the published f/8 78% endpoint is used for optimization and acceptance.'
(R/'target_optimization.json').write_text(json.dumps(target,indent=2),encoding='utf-8')
print('Audited reference knots:',{k:len(v) for k,v in target['data'].items()})
