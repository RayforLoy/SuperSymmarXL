from pathlib import Path
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
from scipy.optimize import brentq
sys.LoadFile(str(ROOT/'models'/'patent_baseline.zmx'),False)
def f(d):
 sys.LDE.GetSurfaceAt(6).Thickness=d;sys.LDE.GetSurfaceAt(7).Thickness=6.06-d
 return sys.MFE.GetOperandValue(Z.Editors.MFE.MeritOperandType.ENPP,0,1,0,0,0,0,0,0)-36.6
root=brentq(f,.1,5.96);print('stop offset from L3',root)
print('exit pupil relative last',sys.MFE.GetOperandValue(Z.Editors.MFE.MeritOperandType.EXPP,0,1,0,0,0,0,0,0)+135.9)
app.CloseApplication()
