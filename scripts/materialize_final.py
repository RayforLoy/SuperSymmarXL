from pathlib import Path
import json
P=Path(__file__).resolve().parents[1]
cp=json.loads((P/'analysis/fit_checkpoint.json').read_text())
exec((P/'scripts/fit_round4.py').read_text().split('count=0;')[0])
apply(cp['x']);outputs={str(fn):calc(fn).tolist() for fn in target}
sys.SystemData.Aperture.ApertureValue=148.1/5.6
sys.LDE.GetSurfaceAt(1).Comment='Reverse engineering candidate; not OEM prescription; see reports'
sys.SaveAs(str(ROOT/'models'/'SuperSymmarXL_150_f5p6_reverse.zmx'))
(ROOT/'analysis'/'fit_result.json').write_text(json.dumps({'x':cp['x'],'base_r':base_r,'outputs':outputs,'termination':'Stopped after numerical plateau: changes far below manual target extraction uncertainty. Acceptance evaluated separately.'},indent=2))
a.Close();app.CloseApplication()
cp=json.loads((P/'analysis/physical_checkpoint.json').read_text())
exec((P/'scripts/fit_physical.py').read_text().split('count=0;')[0])
apply(cp['x']);outputs={str(fn):calc(fn).tolist() for fn in target}
sys.SystemData.Aperture.ApertureValue=148.1/5.6
sys.SaveAs(str(ROOT/'models'/'physical_constrained.zmx'))
(ROOT/'analysis'/'physical_result.json').write_text(json.dumps({'x':cp['x'],'outputs':outputs,'termination':'Numerical plateau; preserved as physically constrained comparison'},indent=2))
a.Close();app.CloseApplication()
