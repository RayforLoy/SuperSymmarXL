from pathlib import Path
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
import System
print([x for x in System.Enum.GetNames(Z.Editors.SolveType) if 'Auto' in x or 'Fix' in x])
sys.LoadFile(str(ROOT/'models'/'physical_constrained.zmx'),False)
print('stop solve',sys.LDE.GetSurfaceAt(7).SemiDiameterCell.GetSolveData().Type)
app.CloseApplication()
