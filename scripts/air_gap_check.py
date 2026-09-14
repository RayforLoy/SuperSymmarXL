from pathlib import Path
p=Path('SuperSymmarXL/scripts/make_reports.py');s=p.read_text(encoding='utf-8')
s=s.replace("r_asph=min(sur[9]", """air=[]
for i,d in enumerate(sur[:-1]):
 if d['glass'] or d['stop'] or sur[i+1]['stop']:continue
 dn=sur[i+1];r=min(d['semi_diameter_mm'],dn['semi_diameter_mm'],abs(d['radius_mm'])*.98,abs(dn['radius_mm'])*.98)
 rr=np.linspace(0,r,1001);gap=d['thickness_mm']+sag(dn,rr)-sag(d,rr)
 air.append({'after_surface':i+1,'assessment_radius_mm':r,'min_axial_air_gap_mm':float(min(gap))})
(P/'analysis/air_gap_screen.json').write_text(json.dumps(air,indent=2))
airmin=min(x['min_axial_air_gap_mm'] for x in air)
r_asph=min(sur[9]""")
s=s.replace('模型半口径包含软件自动估计，不应直接等同于量产外径。','模型半口径包含软件自动估计，不应直接等同于量产外径。\n\n空气间隔另行检查（不含与光阑面相接的段），公共半径范围内的最小轴向间隔为 {airmin:.4f} mm，逐段结果见 air_gap_screen.json。负值表示按当前口径存在表面交叠，必须修订非球面、间距或有效口径；在消除这一问题前不能释放生产。')
p.write_text(s,encoding='utf-8')
