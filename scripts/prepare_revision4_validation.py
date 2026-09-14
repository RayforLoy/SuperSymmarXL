"""Prepare isolated A6 validation tools, without modifying R3 evidence."""
from pathlib import Path
import shutil

S=Path(__file__).parent
R=S.parent/'revision4'
R.mkdir(exist_ok=True)
shutil.copy2(S.parent/'revision3'/'target_optimization.json',R/'target_optimization.json')
for stem in ['validate','curve','audit_mapping','final_integrity','diffraction_bound']:
    source={'audit_mapping':'audit_revision3_mapping.py'}.get(stem,f'{stem}_revision3.py')
    destination={'audit_mapping':'audit_revision4_mapping.py'}.get(stem,f'{stem}_revision4.py')
    if (S/destination).exists():
        print('Preserving existing R4 tool',destination)
        continue
    text=(S/source).read_text(encoding='utf-8').replace('revision3','revision4').replace('R3','R4')
    if stem=='validate':
        text=text.replace("if not any(coef[5:]):coef=coef[:5]", "assert not any(coef[2:]), 'A8 and higher must be zero'\nassert sys.LDE.GetSurfaceAt(10).GetCellAt(12).DoubleValue==0\nassert sys.LDE.GetSurfaceAt(10).Conic==0\ncoef=coef[:2]")
        text=text.replace('asphere_A4_to_A12','asphere_A4_to_A6')
        text=text.replace('R4 reverse candidate','R4 A6 reverse candidate')
        text=text.replace('R4: audited', 'R4: A4/A6 only, A8 and higher zero; audited')
    if stem=='final_integrity':
        text=text.replace("assert np.allclose(coeff,v['asphere_A4_to_A12'],rtol=1e-13,atol=0)", "assert not any(coeff[2:]), 'A8 and higher must be zero'\n  assert sys.LDE.GetSurfaceAt(10).GetCellAt(12).DoubleValue==0\n  assert np.allclose(coeff[:2],v['asphere_A4_to_A6'],rtol=1e-13,atol=0)")
        text=text.replace('seven coefficients','A4/A6 only, zero higher coefficients')
    (S/destination).write_text(text,encoding='utf-8')
print('Prepared isolated R4 validation tools',flush=True)
