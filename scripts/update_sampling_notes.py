from pathlib import Path
p=Path('SuperSymmarXL/scripts/make_reports.py');s=p.read_text(encoding='utf-8')
old='原生输出保留在 native_MTF_f*_512.txt。当前原生输出仍有“取样太低，数据不准确”警告；小幅的 256/512 差值不能单独推翻这一警告，MTF 数值应作为候选分析结果而非已完成数值收敛验收的结果。更高采样复核另存于 high_sampling_check.json 和 native_MTF_f5.6_1024/2048.txt（若计算完成）。'
new='f/8、f/22 的定量结果采用 512 采样且无采样警告。f/5.6 的 512 原生输出曾报告“取样太低，数据不准确”，故补做 1024/2048 复核：更高采样输出已无该警告，1024 与 2048 的最大变化为 {100*v["convergence_1024_2048_f5p6"]:.4f} 个百分点。最终 f/5.6 定量误差采用 2048 结果，其与 512 的最大变化为 {100*v["convergence_512_2048_f5p6"]:.4f} 个百分点。复核数据见 high_sampling_check.json 和 native_MTF_f5.6_1024/2048.txt。'
s=s.replace(old,new).replace('完整数值见 analysis/mtf_comparison.csv','完整数值（f/5.6 为 2048，f/8 与 f/22 为 512）见 analysis/mtf_comparison.csv')
p.write_text(s,encoding='utf-8')
p=Path('SuperSymmarXL/scripts/readme.py');s=p.read_text(encoding='utf-8-sig').replace('python SuperSymmarXL/scripts/dense_mtf.py','python SuperSymmarXL/scripts/high_sampling.py\npython SuperSymmarXL/scripts/apply_high_sampling.py\npython SuperSymmarXL/scripts/dense_mtf.py')
s=s.replace('当前处方不能', '当前处方不能')
s=s.replace('完整验收判据见 analysis/acceptance.json。','完整验收判据见 analysis/acceptance.json。按当前估计口径，非球面后存在约 0.185 mm 的边缘表面交叠，尚不满足制造条件。')
p.write_text(s,encoding='utf-8')
