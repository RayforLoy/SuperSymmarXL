from pathlib import Path
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
sys.LoadFile(str(ROOT/'models'/'patent_baseline.zmx'),False)
for name in ['EFFL','BFL','ENPP','EXPP','EXPD']:
 try: print(name,sys.MFE.GetOperandValue(getattr(Z.Editors.MFE.MeritOperandType,name),0,1,0,0,0,0,0,0))
 except Exception as e:print(str(e)[:100])
for i in range(1,13):
 s=sys.LDE.GetSurfaceAt(i);print(i,s.Radius,s.Thickness,s.Material,s.SemiDiameter,sys.MFE.GetOperandValue(Z.Editors.MFE.MeritOperandType.INDX,i,1,0,0,0,0,0,0))
app.CloseApplication()
