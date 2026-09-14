from pathlib import Path
import shutil
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
REV = ROOT / 'revision2'
manifest = []

def archive(path):
    if path.exists():
        destination = path.parent / 'archive_v1_before_R2' / path.name
        assert path.resolve().is_relative_to(ROOT)
        assert destination.resolve().is_relative_to(ROOT)
        destination.parent.mkdir(exist_ok=True)
        if destination.exists():
            raise RuntimeError(f'Archive already exists: {destination}')
        shutil.move(str(path), str(destination))

def promote(source, destination):
    assert destination.resolve().is_relative_to(ROOT)
    archive(destination)
    shutil.copy2(source, destination)
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert destination.stat().st_size > 0 and digest(source) == digest(destination)
    manifest.append(dict(path=str(destination.relative_to(ROOT)), sha256=digest(destination), bytes=destination.stat().st_size))

for aperture in ('5p6', '8', '22'):
    target = ROOT / 'models' / f'SuperSymmarXL_150_f{aperture}_reverse.zmx'
    for extension in ('.ZDA', '.CFG'):
        archive(target.with_suffix(extension))
    promote(REV / f'SuperSymmarXL_150_R2_f{aperture}.zmx', target)
for title in ('光学性能报告', '生产可能性报告'):
    for extension in ('.pdf', '.md'):
        promote(REV / f'{title}_R2{extension}', ROOT / 'reports' / f'{title}{extension}')
for source, target in [('MTF_full_field.png', 'mtf_comparison.png'), ('section_verified.png', 'lens_section.png')]:
    promote(REV / source, ROOT / 'analysis' / target)
shutil.copy2(ROOT / 'README.md', REV / 'README_before_R2.md')
(ROOT / 'README.md').write_text('''# Super-Symmar XL 150 mm f/5.6 逆向工程 — R2

状态：已修正完整视场与镜片边缘重叠；MTF 仍未全部达到原厂下限，不是原厂等效或生产定版。

## 正式交付
- [f/5.6 ZMX](models/SuperSymmarXL_150_f5p6_reverse.zmx)
- [f/8 ZMX](models/SuperSymmarXL_150_f8_reverse.zmx)
- [f/22 ZMX](models/SuperSymmarXL_150_f22_reverse.zmx)
- [光学性能报告](reports/光学性能报告.pdf)
- [生产可能性报告](reports/生产可能性报告.pdf)
- [完整视场 MTF](revision2/MTF_full_field.png)
- [镜片结构与后组间隙](revision2/section_verified.png)
- [逐点比较](revision2/comparison.csv) / [处方](revision2/prescription.csv)
- [验收结果](revision2/acceptance.json) / [ZMX 重读检查](revision2/zmx_reopen_verification.json)

三档光圈均保留 7 个视场，最大半视场 52.5°、全视场 105°。原厂开大光圈时 MTF 曲线提前终止不代表镜头最大视场变小。光阑使用自动半口径解算，其余表面采用结构图约束的物理通光口径。

后两片保守光学表面检查覆盖半径 15.8 mm，最小空气间隙 0.605 mm；完整机械边缘、倒角和装配结构仍需工程设计。手册结构图与专利轴向布局吻合，可作结构约束，不能视为经过实物测量认证的生产尺寸图。

MTF 优化把原厂曲线作为下限，允许理想模型超过原厂。但审计采样点仍有不足：f/5.6、f/8、f/22 最大短缺分别约 16.0、13.7、10.9 个百分点。报告列出正负偏差和采样收敛检查；不得据此声称全部达到原厂。原厂资料未明确说明这些 MTF 是实测还是理论计算。

## 打开与复算
OpticStudio 顺序模式，mm，无限远物距；原厂六波长和权重，SCHOTT 玻璃目录。本机 OpticStudio 2023 R1 已保存并重新打开验证。缺少历史玻璃时核对 reference/SCHOTT_used_snapshot.AGF，不要无记录替换。

依赖 Python 3.11、numpy、scipy、matplotlib、pythonnet、pymupdf、reportlab 和有效 ZOS-API 许可证。本机安装路径见 scripts/probe_zos.py。从项目目录运行：
```
python SuperSymmarXL/scripts/validate_revision2.py
python SuperSymmarXL/scripts/curve_revision2.py
python SuperSymmarXL/scripts/finalize_revision2_zmx.py
python SuperSymmarXL/scripts/report_revision2.py
```
这些脚本以 revision2/R2_refined.zmx 为输入，更新 revision2 中的结果；正式 models/reports 文件是校验一致的交付副本。promote_revision2.py 是本次一次性归档发布脚本，禁止重复运行。

## 版本和局限
revision2 保存本轮完整证据和过程。models/reports/analysis 的 archive_v1_before_R2 保存被替换文件。analysis 中除两个已更新的稳定图像链接外，其余数据及旧版验证、报告脚本属于 V1 历史，不应用于评价或覆盖 R2。旧版 README 存于 revision2/README_before_R2.md。

MTF 不足以唯一恢复处方。非球面、玻璃替代、机械遮挡、镀膜、近摄性能、完整公差和量产良率仍未完成验证。所有项目输出均留在 SuperSymmarXL 文件夹内。
''', encoding='utf-8')
(REV / 'delivery_manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(manifest, indent=2, ensure_ascii=False))
