from pathlib import Path
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
import json
R=ROOT/'revision2';record=[]
for fn in ['5p6','8','22']:
 p=R/('SuperSymmarXL_150_R2_f'+fn+'.zmx');sys.LoadFile(str(p),False)
 sys.SystemData.TitleNotes.Title='Super-Symmar XL 150 mm - R2 reverse candidate - full 105 deg'
 sys.SystemData.TitleNotes.Author='Reverse engineering study'
 sys.SystemData.TitleNotes.Notes='R2: complete 105 degree field at all apertures. Drawing-derived clear apertures participate in ray tracing. Stop semi-diameter is automatic. No nominal surface overlap within checked apertures. Some MTF samples remain below manufacturer reference; not a production release. See revision2 reports.'
 assert str(sys.SystemData.Fields.GetFieldType())=='Angle'
 fields=[sys.SystemData.Fields.GetField(i).Y for i in range(1,sys.SystemData.Fields.NumberOfFields+1)]
 assert max(fields)==52.5 and len(fields)==7
 assert str(sys.LDE.GetSurfaceAt(7).SemiDiameterCell.GetSolveData().Type)=='Automatic'
 assert sys.LDE.GetSurfaceAt(10).SemiDiameter==15.5
 assert sys.LDE.GetSurfaceAt(11).SemiDiameter==14
 assert sys.LDE.GetSurfaceAt(12).SemiDiameter==18.8
 sys.Save();sys.LoadFile(str(p),False)
 assert max(sys.SystemData.Fields.GetField(i).Y for i in range(1,8))==52.5
 record.append({'file':p.name,'field_angles_deg':fields,'entrance_pupil_mm':sys.SystemData.Aperture.ApertureValue,'focal_length_mm':sys.MFE.GetOperandValue(Z.Editors.MFE.MeritOperandType.EFFL,0,1,0,0,0,0,0,0)})
(R/'zmx_reopen_verification.json').write_text(json.dumps(record,indent=2));app.CloseApplication();print('All three native ZMX files reopened: full 105 deg, 7 fields, automatic stop, fixed apertures.')
