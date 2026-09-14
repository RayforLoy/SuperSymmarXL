from pathlib import Path
p=Path('SuperSymmarXL/scripts/validate_export.py');s=p.read_text().replace('for i in [13,14,15]]','for i in [13,14,15,16,17]]').replace("'asphere_A4_A6_A8':asph", "'asphere_A4_A6_A8_A10_A12':asph")
s=s.replace("'semi_diameter_mm':s.SemiDiameter", "'semi_diameter_mm':s.SemiDiameter")
p.write_text(s)
p=Path('SuperSymmarXL/scripts/make_reports.py');s=p.read_text(encoding='utf-8-sig').replace("v['asphere_A4_A6_A8']","v['asphere_A4_A6_A8_A10_A12']").replace('[4,6,8]','[4,6,8,10,12]').replace('a4,a6,a8=','a4,a6,a8,a10,a12=').replace('+A8 r⁸，','+A8 r⁸+A10 r¹⁰+A12 r¹²，').replace('其余高阶项为零。','A10={a10:.12g} mm^-9，A12={a12:.12g} mm^-11。其余高阶项为零。').replace('A4/A6/A8 数值','非球面系数数值')
p.write_text(s,encoding='utf-8')
# Preserve the exact glass records used, not a supplier availability claim.
raw=Path(r'C:\Users\liuru\Documents\Zemax\Glasscat\SCHOTT.AGF').read_text(errors='ignore')
keep=False;out=['CC Snapshot of the five glass records used in the reverse model; source hash in sources.json']
for line in raw.splitlines():
 if line.startswith('NM '):keep=line.split()[1] in ['KF9','N-LAK33B','N-SK5','F2','K10']
 if keep:out.append(line)
Path('SuperSymmarXL/reference/SCHOTT_used_snapshot.AGF').write_text('\n'.join(out)+'\n')
