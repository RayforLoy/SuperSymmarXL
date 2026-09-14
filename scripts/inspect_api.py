exec(open(__file__.replace('inspect_api.py','probe_zos.py')).read().split("print('system'")[0])
import System
asm=System.Reflection.Assembly.LoadFrom(str(ZDIR/'ZOSAPI_Interfaces.dll'))
for t in asm.GetTypes():
 if any(k in t.FullName for k in ['IAS_FftMtf','RayAimingMethod','RayAimingType']):
  print(t.FullName, [p.Name for p in t.GetProperties()]);print([str(x) for x in t.GetFields()])
app.CloseApplication()
