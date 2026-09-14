from pathlib import Path
p=Path('SuperSymmarXL/scripts/validate_revision2.py');s=p.read_text();s=s.split('# Continuous-field graph sampling')[0]+'app.CloseApplication()\n';p.write_text(s)
p=Path('SuperSymmarXL/scripts/report_revision2.py');s=p.read_text(encoding='utf-8');s=s.replace('读图误差约 2-4 个百分点，不能把最后一位小数当作原厂精度。','读图误差约 2-4 个百分点，不能把最后一位小数当作原厂精度。RMSE 同时统计高于和低于原厂的差异；本轮主要使用最大低于原厂幅度与达到下限的样点数判定，不把超额性能当作主要缺陷。')
p.write_text(s,encoding='utf-8')
