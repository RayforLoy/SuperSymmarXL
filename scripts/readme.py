from pathlib import Path
import json
P=Path(__file__).resolve().parents[1]
a=json.loads((P/'analysis/acceptance.json').read_text())
status='通过本轮离散 MTF 筛选（仅无限远已采样条件）' if a['pass'] else '尚未通过 MTF 等效筛选；不可称为原厂等效或生产定版'
text=f'''# Super-Symmar XL 150 mm f/5.6 逆向工程

状态：**{status}**。

## 主要交付
- [f/5.6 逆向 ZMX](models/SuperSymmarXL_150_f5p6_reverse.zmx)
- [f/8 ZMX](models/SuperSymmarXL_150_f8_reverse.zmx)
- [f/22 ZMX](models/SuperSymmarXL_150_f22_reverse.zmx)
- [光学性能报告 PDF](reports/光学性能报告.pdf) / [Markdown](reports/光学性能报告.md)
- [生产可能性报告 PDF](reports/生产可能性报告.pdf) / [Markdown](reports/生产可能性报告.md)
- [MTF 叠图](analysis/mtf_comparison.png)
- [处方表](analysis/prescription.csv) / [逐点 MTF 误差](analysis/mtf_comparison.csv)

本轮总体 MTF RMSE 为 {a['overall']['rmse']*100:.2f} 个百分点；最大绝对偏差 {a['overall']['max_abs']*100:.2f} 个百分点。原厂扫描图的人工读数仍有约 2–4 个百分点不确定度。完整验收判据见 analysis/acceptance.json。按当前估计口径，非球面后存在约 0.185 mm 的边缘表面交叠，尚不满足制造条件。

## 如何打开
用 OpticStudio 顺序模式打开 models 下的 ZMX，单位为 mm，物距为无限远。主波长为 546 nm，包含原厂六波长和权重；玻璃引用 SCHOTT 目录。文件在本机 OpticStudio 2023 R1 通过 ZOS-API 保存并重新读取进行计算。

若其他电脑提示 KF9 等玻璃缺失，请核对 reference/SCHOTT_used_snapshot.AGF 和 reference/sources.json 中的目录记录。不要默默替换牌号或把专利 ne 当作 nd。快照用于复现，并不证明当前可采购。

## 复算
本机使用 Python 3.11，依赖 numpy、scipy、matplotlib、pythonnet、pymupdf、reportlab，以及可用的 OpticStudio API 许可证。scripts/probe_zos.py 中记录了本机安装路径，迁移电脑时需要调整该路径。

在项目目录运行：
```
python SuperSymmarXL/scripts/validate_export.py
python SuperSymmarXL/scripts/high_sampling.py
python SuperSymmarXL/scripts/apply_high_sampling.py
python SuperSymmarXL/scripts/dense_mtf.py
python SuperSymmarXL/scripts/make_reports.py
python SuperSymmarXL/scripts/readme.py
```

validate_export.py 对最终 ZMX 做 FFT 256/512 对比、导出原生文本及单项敏感性试算。dense_mtf.py 导出原生 MTF 随视场分析。脚本会更新本文件夹中的分析结果与报告。

## 文件组织与局限
reference 保存原始资料的渲染、校验值和目录快照；models 保存基线、实验及最终候选；analysis 保存计算和拟合过程；reports 保存交付报告；scripts 保存可复现程序。所有项目产出均在本文件夹内。

patent_baseline 是缺失非球面系数时的专利基线；seed/axis/round* 是逆向过程，不是量产版本。aperture_trial 仅为通光口径试验，不是最终模型。最终处方不能由 MTF 唯一确定；未完成近摄倍率、镀膜透射率、照度、完整机械遮挡和完整公差/良率验证，详见报告。
'''
(P/'README.md').write_text(text,encoding='utf-8')
