from pathlib import Path
p=Path('SuperSymmarXL/scripts/validate_export.py');s=p.read_text()
s=s.replace('def get(fn,sampling):\n sys.SystemData', '''def get(fn,sampling):
 n=len(target['data'][str(fn)])
 while sys.SystemData.Fields.NumberOfFields>n:sys.SystemData.Fields.RemoveField(sys.SystemData.Fields.NumberOfFields)
 while sys.SystemData.Fields.NumberOfFields<n:
  idx=sys.SystemData.Fields.NumberOfFields;sys.SystemData.Fields.AddField(0,193*target['heights'][idx],1)
 sys.SystemData''')
s=s.replace("sys.SaveAs(str(ROOT/'models'/'SuperSymmarXL_150_f5p6_reverse.zmx'))", "while sys.SystemData.Fields.NumberOfFields>5:sys.SystemData.Fields.RemoveField(sys.SystemData.Fields.NumberOfFields)\nsys.SaveAs(str(ROOT/'models'/'SuperSymmarXL_150_f5p6_reverse.zmx'))")
p.write_text(s)
