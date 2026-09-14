from pathlib import Path
import argparse,json
import optimize_revision3 as optical

parser=argparse.ArgumentParser();parser.add_argument('checkpoint');parser.add_argument('--output',default='checkpoint_export.zmx');args=parser.parse_args()
record=json.loads(Path(args.checkpoint).read_text())
optical.initialize(record['seed'],record.get('sampling',256),record['target'],True,record.get('axis_focus_enforced',False))
try:
 residual,final=optical.evaluate(record['x'],str(optical.R/args.output))
 (optical.R/args.output.replace('.zmx','_audit.json')).write_text(json.dumps(final,indent=2),encoding='utf-8')
 print('Exported native checkpoint',args.output,'shortfall',final['max_shortfall'],flush=True)
finally:optical.app.CloseApplication()
