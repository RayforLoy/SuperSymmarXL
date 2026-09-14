# 夜间材料替代与制造降本证据

2026-09-15；只读本机目录并冻结快照，未启动原生 Zemax 实例。计划采用真实具名 SCHOTT/CDGM 玻璃的 CD 色散式，六个模拟波长为 546、644、588、480、436、405nm，保留原厂权重。`catalog_plan.json` 每片给出五个候选，混合与全 CDGM 各二十个初始种子；后续采用单片邻域与宽度四的 beam，避免 5^6 穷举。两个原 N-LAK33B 片可独立选择。

## 可直接执行的两种全 CDGM 起点

| 片 / 顺序面 | 原材料 | 最接近完整色散起点 | 同片候选中较低 OD 起点 |
|---|---|---|---|
| L1 / S1 | KF9 | H-KF6 | H-K51 |
| L2 / S3 | N-LAK33B | H-LAK53B | H-LAK53B |
| L3 / S5 | N-LAK33B | H-LAK53B | H-LAK53B |
| L4 / S8 | N-SK5 | H-ZK3A | H-ZK3A |
| L5 / S9 | F2 | F4GTI | H-F4 |
| L6 / S11 | K10 | H-K1 | H-K10 |

这些不是等效处方。按全部六波长和权重，H-LAK53B 相对原正片的折射率 RMS 差约 2.06×10^-6，H-ZK3A 相对 N-SK5 约 2.18×10^-6；H-KF6 相对 KF9 约 0.00608，H-K1 相对 K10 约 0.00214，外侧负片不能只换玻璃而期待原 MTF 不变。`material_manifest.json` 保存每个具名材料的完整 CD/LD、标准谱线 n、六波长 n、相对部分色散及每片替换差值。

## 价格与供应证据边界

本机 CDGM 目录首行标明 2022 年 6 月更新，SCHOTT 标明状态日期 2022-10-27。目录含 OD 相对成本，NM 标准/优选/废弃状态及熔炼频次编码。[Ansys AGF 格式文档](https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v251/en/OpticStudio_User_Guide/OpticStudio_Help/topics/The_AGF_BGF_File_Formats.html)说明这些字段的意义，也明确 n、V 参考值不替代实际 CD 色散式。所有替代候选仅从标准/优选且未排除替代的材料选取；保留原材料只用于基线。

原 KF9 在冻结 SCHOTT 目录中为 status=2（Obsolete），因此混合方案保留它只用于原处方参照；N-KF9 是一项优先检验的具名替代。其它原材料在本机目录为 Preferred，但这些仍是 2022 状态，不能当作 2026 库存确认。KF9 的停产状态也不证明旧库存绝对不存在。

本机 CDGM OD 中，F4GTI 为 45.9、H-F4 为 1.6；H-LAK53B 为 5.5、H-LAK53A 为 11.6；H-K1 为 12.6、H-K10 为 3.6。它们可支持同一冻结 CDGM 目录内部的粗筛优先级，因此单纯采用最接近色散的 F4GTI/H-K1 不应自动称为低成本组合。这些数值不是人民币价格，也不是当前供应商报价，不对应加工费。未核实跨厂目录采用同一成本基准，禁止把 SCHOTT/CDGM OD 比值转成节省百分比；方案的绝对价格与节省百分比均为 null。

[CDGM 厂家下载入口](https://www.cdgmgd.com/go.htm?k=Download&url=downList)提供原厂 Zemax/PDF/Excel 资料；[SCHOTT 原厂下载入口](https://www.schott.com/en-us/products/optical-glass-p1000267/downloads)区分标准目录与 inquiry glasses。这些支持目录模型真实性，但不能证明特定玻璃、熔次、80mm 以上外径毛坯或本次数量在库。未联系供应商；当前可供形状、直径、数量、交期和熔次均需单独核实。

## 制造降本可以评估什么

优先比较同厂普通等级材料与高透过/特殊等级材料，在保留六波长性能后再评估目录内部 OD；尽量共用两个正片的同一玻璃，只有分开选择确有光学收益时才增加玻璃品种。少一种材料可能减少采购与熔次管理工作，这是生产规划推论，尚无费用数据证明节省金额。

[CDGM 成像非球面产品页](https://www.cdgmgd.com/go.htm?k=Imaging_Aspherical_Lens&url=goods)公布直径 ≤40mm 的超精密模压能力。S10 名义通光直径约 31mm 的尺寸落在该宽泛范围中，只能说明值得询问；不能证明当前玻璃可模压、该胶合组曲面满足工具与脱模限制或所公开的通用误差足以满足本镜头 MTF。原厂年代加工路线仍参见 `revision4/historical_manufacturing_audit.md`，不得以今天模压产品页面反推 1996 年 XL 实物工艺。

每个组合须用实际具名目录玻璃原生复算，保持 A4/A6、全 105°、共同像面、固定物理口径及无交叠，再评价 MTF、色差、透过率、坡度、球面离差、边厚和装调敏感性。完整色散接近不保证 MTF，低多项式阶数不保证加工成本；全 CDGM 是采购约束方案，降本效果需有同规格毛坯、加工、检测及装配报价后才可确认。

## 冻结文件

- `reference/CDGM_20260915_snapshot.AGF` 与 `reference/SCHOTT_20260915_snapshot.AGF`：按本机原件逐字节复制，hash 写入两份 JSON。
- `catalog_plan.json`：阶段、面号、候选、局部组合与 beam 策略；全 CDGM 阶段所有六项目录均为 CDGM。
- `material_manifest.json`：仅三十五种实际候选/原材料，完整目录数据与六波长/部分色散差异；未实现公式或有效波段/参考 n,V 检查失败的条目已明确排除。

没有建立 nd/Vd model glass，也没有把目录模型当成已确认现货或原厂历史材料身份。
