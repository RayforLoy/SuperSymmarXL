from pathlib import Path
p=Path('SuperSymmarXL/scripts/make_reports.py');s=p.read_text(encoding='utf-8')
s=s.replace("  ax.scatter(h,ref[:,2*k+j],marker='x' if j==0 else 'o',facecolors=colors[k] if j==0 else 'none',edgecolors=colors[k],s=27)","  if j==0:ax.scatter(h,ref[:,2*k+j],marker='x',color=colors[k],s=27)\n  else:ax.scatter(h,ref[:,2*k+j],marker='o',facecolors='none',edgecolors=colors[k],s=27)")
s=s.replace('结论：可以作为定制光学样机的设计研究起点；当前不能释放为生产图纸或作出良率保证。','结论：当前候选未通过按现有有效口径的几何制造筛查，非球面后的最小空气间隔为 {airmin:.4f} mm，出现表面交叠。必须先修订处方或有效口径并重新验证覆盖范围，不能据此加工装配或作出良率保证。')
s=s.replace('原生输出保留在 native_MTF_f*_512.txt，包含软件发出的任何警告。','原生输出保留在 native_MTF_f*_512.txt。当前原生输出仍有“取样太低，数据不准确”警告；小幅的 256/512 差值不能单独推翻这一警告，MTF 数值应作为候选分析结果而非已完成数值收敛验收的结果。更高采样复核另存于 high_sampling_check.json 和 native_MTF_f5.6_1024/2048.txt（若计算完成）。')
s=s.replace('当前建议为“继续设计与样机验证”','当前建议为“先消除表面交叠并重新拟合，随后才考虑样机验证”')
p.write_text(s,encoding='utf-8')
