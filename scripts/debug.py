from pathlib import Path
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
import System
for t in System.Reflection.Assembly.LoadFrom(str(ZDIR/'ZOSAPI_Interfaces.dll')).GetTypes():
 if 'ZemaxApertureType' in t.FullName:print(t.FullName,[str(x) for x in t.GetFields()])
sys.LoadFile(str(ROOT/'models'/'axis_optimized.zmx'),False)
print('aper',sys.SystemData.Aperture.ApertureType,sys.SystemData.Aperture.ApertureValue,'stop',sys.LDE.GetSurfaceAt(7).SemiDiameter)
for name in ['REAY','RAGY','RSCE']:
 for p in [.01,.5,1]:
  print(name,p,sys.MFE.GetOperandValue(getattr(Z.Editors.MFE.MeritOperandType,name),7,1,0,0,0,p,0,0))
app.CloseApplication()
