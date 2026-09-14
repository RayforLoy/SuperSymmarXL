from pathlib import Path
p=Path('SuperSymmarXL/scripts/make_reports.py');s=p.read_text(encoding='utf-8')
s=s.replace('近轴后焦距与实际最佳像面位置是不同量。','近轴后焦距与实际最佳像面位置是不同量。入瞳位置计算值 {fo["ENPP"]:.5f} mm（原厂 36.6 mm），出瞳相对末面的计算位置 {fo["EXPP"]+sur[-1]["thickness_mm"]:.5f} mm（原厂 -16.1 mm）。\n\n补充约束：在未改变专利曲率/厚度时，用原厂入瞳位置可反求光阑位于第三片后表面后 4.839901 mm，且出瞳计算为 -16.14464 mm。physical_constrained.zmx 保留了按这一约束重拟合的候选；主交付仍按已完成的 MTF 对比结果选择。')
s=s.replace('光阑精确位置，因此这些不能视为已知原厂参数。','光阑精确位置；光阑位置可利用原厂瞳位置另行反求，但不应视为实物测量值。')
p.write_text(s,encoding='utf-8')
