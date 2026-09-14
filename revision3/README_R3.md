# Super-Symmar XL 150 mm f/5.6 逆向工程 — R3

状态：完成本轮均衡优化与原生 FFT 复核，仍未达到所有对照点优于原厂，不是原厂认证处方或生产定版。

## 当前交付

- [f/5.6 ZMX](models/SuperSymmarXL_150_f5p6_reverse.zmx)
- [f/8 ZMX](models/SuperSymmarXL_150_f8_reverse.zmx)
- [f/22 ZMX](models/SuperSymmarXL_150_f22_reverse.zmx)
- [合并光学性能与制造可能性报告](reports/光学性能与制造可能性报告.pdf)
- [完整视场 MTF 对比](analysis/mtf_comparison.png)
- [结构与后组间隙](analysis/lens_section.png)
- [逐点 MTF](revision3/comparison.csv) / [完整处方](revision3/prescription.csv)
- [验收记录](revision3/acceptance.json) / [ZMX 重读记录](revision3/zmx_reopen_verification.json)

三档光圈均为 7 个视场，最大半视场 52.5°，全视场 105°，共同末面像距 135.222518763499 mm。固定原结构图约束的通光口径，光阑半口径自动解算。共同像面按 f/5.6 轴上 20 lp/mm 最大化获得；256 采样的 ±0.2 mm 局部扫描最佳点与正式像面重合。

S10 采用 A4 至 A16 七项偶次非球面。保守延伸到半径 15.8 mm 的 S10–S11 检查最小空气间隙 0.565544 mm，六片玻璃在共同光学口径内均为正厚度。连接不同光学口径的直线边缘是示意，完整倒角、机械外缘和装配公差未定义。

## MTF 判定

使用本轮重新审核的 186 项手册近似数字化读数，原厂六波长及权重，5、10、20 lp/mm，T 为虚线、S 为实线。图中模拟用蓝／青／绿，手册用橙／红／紫，全为线条，无圈或叉。公开曲线以外不推定原厂 MTF 为零。

| 光圈 | 同条件 R2 最大不足，百分点 | R3 最大不足，百分点 | R3 采样 |
|---|---:|---:|---:|
| f/5.6 | 18.065 | 13.252 | 1024 |
| f/8 | 8.403 | 3.937 | 512 |
| f/22 | 13.781 | 7.478 | 512 |

R2 基线重新按本轮目标和聚焦规则复算，使用 256 采样。R3 高采样相对 256 的最大变化分别为 0.194、0.113、0.114 个百分点。104/186 项达到或超过近似原厂读数；尚有不足，尤其 f/5.6 40% 参考视场的 5 lp/mm S 方向。读图误差不能替代严格达标。

真实光线审核发现像高与 193h mm 的映射存在约 1.2% 的相对差异；完整系统边缘真实主光线像高约 192.378 mm。严格同像高对照仍需重新指定场点。全视场几何瞳通光份额约为 17.9%、36.9%、100%，不能等同照度。原生相对照度、工作 f 数和多波长记录见报告及 mapping_pupil_focus_audit.json。

Huygens 交叉检查存在采样与窗口收敛问题；其较高数值不能用于宣称优于原厂。最终 FFT 数值只是在明确条件下的名义计算，尚需完成独立计算有效性、公差、装配补偿和样机验证。

## 打开与复算

OpticStudio 顺序模式，mm，无限远物距，SCHOTT 玻璃目录，有效 ZOS-API 许可证。本机 OpticStudio 2023 R1 已重新打开三文件，验证完整视场、固定口径、Real 光线瞄准和共同像面。缺少玻璃时核对 reference/SCHOTT_used_snapshot.AGF，记录任何替换。

依赖 Python 3.11、numpy、scipy、matplotlib、pythonnet、pymupdf、reportlab。安装路径见 scripts/probe_zos.py。复算写入 revision3，不自动覆盖正式副本：

```powershell
python SuperSymmarXL/scripts/validate_revision3.py --input agent_search/higher7_asphereonly1_best.zmx
python SuperSymmarXL/scripts/curve_revision3.py --input agent_search/higher7_asphereonly1_best.zmx
python SuperSymmarXL/scripts/audit_revision3_mapping.py --model SuperSymmarXL/revision3/agent_search/higher7_asphereonly1_best.zmx
python SuperSymmarXL/scripts/manufacturing_metrics_revision3.py
python SuperSymmarXL/scripts/report_revision3.py
```

报告生成需遵循 PDF 技能的操作标记与全页渲染检查。promote_revision3.ps1 是本次一次性归档发布脚本，不应重复运行。

## 证据和版本

revision3 保存本轮原生 MTF、处方、密集手册目标、瞳面/像高/聚焦、制造几何、Huygens 诊断及搜索记录。正式候选来源为 revision3/agent_search/higher7_asphereonly1_best.zmx；五项宏优化和弯曲分支保留用于追溯。revision2 和 archive_R2_before_R3 保存 R2。旧版本数据不得用来覆盖或评价本轮。

公开 MTF 和结构图不能唯一恢复原厂实际处方。生产采购、完整机械结构、镀膜、公差与良率尚未完成。所有产出保存在 SuperSymmarXL 文件夹内。
