from pathlib import Path
import json
p=Path('SuperSymmarXL/scripts/make_reports.py');s=p.read_text(encoding='utf-8')
s=s.replace("passed=all(e['rmse']", "conic=json.loads((P/'analysis/conic_result.json').read_text())\nphysical=json.loads((P/'analysis/physical_result.json').read_text())\nphysical_rmse=float(np.sqrt(np.mean(np.concatenate([(np.array(physical['outputs'][fn])-t['data'][fn]).ravel() for fn in ['5.6','8','22']])**2)))\npassed=all(e['rmse']")
s=s.replace('MTF 拟合存在非唯一性。','补充候选比较：严格保留专利尺寸并由瞳位置约束光阑的高阶非球面候选，整体离散 MTF RMSE 约 {100*physical_rmse:.2f} 个百分点；低阶纯圆锥面候选的整体 RMSE 约 {100*conic["rmse"]:.2f} 个百分点。这些替代尝试也未解决全部目标。另行限制第三片通光半径的试算仍保留约 11 个百分点的全开 RMSE，故未据此替换主候选。\n\n主波长近轴畸变样点（像高 mm / 百分比）为：{", ".join(format(d["height_mm"],".1f")+" / "+format(d["distortion_pct"],".3f") for d in v["distortion"])}。六波长近轴后焦距最大跨度约 {max(fo["wave_"+str(i)]["bfl"] for i in range(1,7))-min(fo["wave_"+str(i)]["bfl"] for i in range(1,7)):.4f} mm；这是近轴色焦移指标，不是实测最佳焦面色差。\n\nMTF 拟合存在非唯一性。')
p.write_text(s,encoding='utf-8')
