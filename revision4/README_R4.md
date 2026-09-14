# Super-Symmar XL 150 mm f/5.6 - R4，最高 A6

本轮已按用户要求重新优化低阶非球面，所有图例在绘图区外。三档原生 ZMX 只在 S10 使用 A4、A6；A2、A8 及更高项为零，全部光学面的圆锥常数为零。没有直接截断旧系数并沿用旧 MTF。

最终源为 `revision4/agent_search/a6_stage2_candidate_e6.zmx`，SHA256：`bc8d56c9b2e2141f725d37f657917e2a31f0a2a6f4aebf79d86a689f6c4095be`。

## 当前交付

- `models/SuperSymmarXL_150_f5p6_reverse.zmx`
- `models/SuperSymmarXL_150_f8_reverse.zmx`
- `models/SuperSymmarXL_150_f22_reverse.zmx`
- `reports/光学性能与制造可能性报告.pdf`，10页，已逐页渲染检查。
- `reports/光学性能与制造可能性报告.md`
- `analysis/mtf_comparison.png`，模拟蓝/青/绿、手册橙/红/紫；S实线、T虚线，无点标记。
- `analysis/lens_section.png`

## 真实验收结果

全部光圈保持 Angle 最大半视场52.5°、全视场105°，固定结构图口径、自动光阑和六波长权重。三档共同像距135.408789815897mm，按f/5.6轴上20lp/mm峰值定焦，256采样局部扫描最佳点为正式像面。

| 光圈 | 定量FFT采样 | 最大低于手册读数，百分点 | 严格达到读数 |
| --- | --- | --- | --- |
| f/5.6 | 1024 | 10.591 | 21/48 |
| f/8 | 512 | 7.669 | 47/60 |
| f/22 | 512 | 9.674 | 36/78 |

**尚未达到全部MTF高于原厂的目标。** 手册来自密集人工读图，不是原厂数值表。完整绘图采用FFT512；高采样相对256的最大变化分别为0.111、0.097、0.104个百分点。实际主波长完整视场主光线像高192.820469mm，公开对照区最大相对映射偏差约1.041%；严格同实际像高比较仍需进一步处理。

原生重新打开三份文件，逐面类型、系数、半径、距离、材料、口径、共同像面和视场已核对，记录见 `revision4/final_integrity.json`。后组在15.8mm半径保守域的最小间隙0.670915mm；六片共同有效口径内最小厚度均为正。此项不替代机械边缘及制造公差检查。

## 年代制造与计算边界

S10有效半径15.5mm，相对指定顶点半径球面的设计偏离PV为228.326μm；仅A4/A6并不能证明原厂阶数或年代可制造性。合并报告结合施耐德数控抛光、CGH检测与反馈修形主源，讨论了年代证据、面形斜率、边缘厚度、材料、检测和装调要求。尚无完整公差、Monte Carlo良率或样机验证，不是生产放行处方。

本轮A6的五场点Huygens抽查使用同一源及共同像面，image512、间距1μm，pupil128与256。两级最大变化4.309个百分点，仍未收敛；与FFT512最大差13.355个百分点。结果不能用于证明全部性能优于原厂。详情见本轮 `huygens_spot_p128.json`、`huygens_spot_p256.json` 和报告。

正式模型、报告和两张分析图的R3版本保存在各目录 `archive_R3_before_R4`；R3完整资料仍在 `revision3`。本轮早期e2的原生验证数据单独保存在 `revision4/preliminary_e2`，未混用于最终e6报告。全部产出位于SuperSymmarXL文件夹。

## 复算

1. `scripts/validate_revision4.py --input agent_search/a6_stage2_candidate_e6.zmx`
2. `scripts/curve_parallel_revision4.py --workers 4`
3. `scripts/audit_revision4_mapping.py` 与 `scripts/final_integrity_revision4.py`
4. `scripts/manufacturing_metrics_revision4.py`
5. 两级本轮Huygens抽查及 `scripts/report_revision4.py`；创建或编辑PDF前先执行PDF技能artifact marker，之后渲染检查全部页面。

辅助数据与冻结源SHA256绑定，制造记录还绑定十二面处方及轮廓图。身份缺失或不匹配时，报告拒绝必需曲线数据并不引用可选旧数据。不要重复运行一次性 `promote_revision4.ps1`。
