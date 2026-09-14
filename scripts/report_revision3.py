"""Build the single R3 report after final Zemax validation.

Run only after the PDF artifact-operation marker has succeeded. This script does
not connect to Zemax, optimize, or substitute a nominal result for measured data.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

P = Path(__file__).resolve().parents[1]
R = P / 'revision3'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def heights_for(obj, fn, rows, fallback=None):
    h = obj.get('heights_by_aperture', {}).get(fn, obj.get('heights'))
    if h is not None and len(h) >= rows:
        return np.asarray(h[:rows], dtype=float)
    angles = obj.get('field_angles_deg')
    if angles is not None and len(angles) >= rows:
        angles = angles[:rows]
        h = np.tan(np.radians(angles)) * 148.1 / 193.0
        h[-1] = 1.0 if abs(angles[-1] - 52.5) < .001 else h[-1]
        return h
    if fallback is not None and len(fallback) == rows:
        return np.asarray(fallback, dtype=float)
    raise ValueError(f'No explicit height grid for f/{fn}, {rows} rows')


def main():
    v = read(R / 'validated.json')
    target = read(R / v.get('target_file', 'target_optimization.json'))
    curves = read(R / 'field_curves.json')
    dc = read(P / 'revision2' / 'drawing_constraints.json')
    old = read(P / 'revision2' / 'validated.json')
    sur = v['surfaces']
    coef = np.asarray(v.get('asphere_A4_to_A16', v.get('asphere_A4_to_A12', [])), dtype=float)
    assert len(sur) == 12 and len(coef) in [5, 6, 7]
    powers = np.arange(4, 4 + 2 * len(coef), 2)
    old_coef = np.asarray(old.get('asphere_A4_to_A16', old['asphere_A4_to_A12']), dtype=float)
    old_coef = np.pad(old_coef, (0, max(0, len(coef) - len(old_coef))))[:len(coef)]
    audit_path = R / 'mapping_pupil_focus_audit.json'
    audit = read(audit_path) if audit_path.exists() else None
    manufacturing_path = R / 'manufacturing_geometry_metrics.json'
    manufacturing = read(manufacturing_path) if manufacturing_path.exists() else None
    diffraction_path = R / 'diffraction_reference.json'
    diffraction = read(diffraction_path) if diffraction_path.exists() else None
    z = np.cumsum([0.] + [s['thickness_mm'] for s in sur[:-1]])

    def sag(i, radius):
        s = sur[i - 1]
        r = np.asarray(radius, dtype=float)
        rad = float(s['radius_mm'])
        k = float(s.get('conic', v.get('asphere_conic', 0) if i == 10 else 0))
        if np.isfinite(rad):
            disc = 1 - (1 + k) * (r / rad) ** 2
            if np.any(disc < 0):
                raise ValueError(f'Surface {i}: undefined sag in checked aperture')
            out = r * r / (rad * (1 + np.sqrt(disc)))
        else:
            out = np.zeros_like(r)
        if i == 10:
            out += sum(a * r ** int(p) for a, p in zip(coef, powers))
        return out

    geometry = []
    for first, second in [(2, 3), (4, 5), (6, 8), (10, 11)]:
        radius = min(sur[first - 1]['clear_radius_mm'], sur[second - 1]['clear_radius_mm'])
        if first == 10:
            radius = sur[first - 1]['clear_radius_mm'] + .3
        rr = np.linspace(0, radius, 10001)
        gap = z[second - 1] - z[first - 1] + sag(second, rr) - sag(first, rr)
        geometry.append({'after_surface': first, 'before_surface': second,
                         'checked_radius_mm': float(radius), 'min_gap_mm': float(gap.min()),
                         'at_radius_mm': float(rr[np.argmin(gap)]),
                         'conservative_extension': first == 10})
    glass_geometry = []
    for first in [1, 3, 5, 8, 9, 11]:
        second = first + 1
        radius = min(sur[first - 1]['clear_radius_mm'], sur[second - 1]['clear_radius_mm'])
        rr = np.linspace(0, radius, 10001)
        thick = sur[first - 1]['thickness_mm'] + sag(second, rr) - sag(first, rr)
        glass_geometry.append({'front_surface': first, 'rear_surface': second,
                               'checked_radius_mm': float(radius), 'min_thickness_mm': float(thick.min())})
    min_gap = min(g['min_gap_mm'] for g in geometry)
    no_overlap = min_gap > 0 and min(g['min_thickness_mm'] for g in glass_geometry) > 0
    geometry_output = {'air_gaps': geometry, 'glass_thickness_checks': glass_geometry,
                       'min_air_gap_mm': min_gap, 'no_surface_intersection_in_checked_regions': no_overlap,
                       'rear_aperture_readout_allowance_mm': .3,
                       'scope': 'Optical surface geometry; not a mechanical tolerance guarantee.'}
    (R / 'geometry_verified.json').write_text(json.dumps(geometry_output, indent=2), encoding='utf-8')

    fig, axs = plt.subplots(1, 2, figsize=(13, 5.8), gridspec_kw={'width_ratios': [1.6, 1]})
    for ax in axs:
        for i, su in enumerate(sur[:-1]):
            if not su['glass']:
                continue
            yf = np.linspace(-su['clear_radius_mm'], su['clear_radius_mm'], 401)
            yb = np.linspace(sur[i + 1]['clear_radius_mm'], -sur[i + 1]['clear_radius_mm'], 401)
            verts = np.c_[np.r_[z[i] + sag(i + 1, yf), z[i + 1] + sag(i + 2, yb)], np.r_[yf, yb]]
            ax.add_patch(Polygon(verts, fc='#d4eaf7', ec='#233c4d', lw=1.1))
        ax.axhline(0, color='#71808b', lw=.6)
        ax.axvline(z[6], color='#b25a20', ls='--', lw=1)
        ax.set_aspect('equal')
        ax.set(xlabel='Axial distance (mm)', ylabel='Radius (mm)')
        ax.grid(alpha=.13)
    axs[0].set(xlim=(-4, max(82, z[-1] + 4)), ylim=(-44, 44), title='R3 optical section: full 105-degree field')
    axs[1].set(xlim=(z[7] - 2, z[-1] + 3), ylim=(-20, 20), title='Rear groups: checked surface geometry')
    fig.suptitle('Straight optical-edge connections are schematic, not production mechanical dimensions', fontsize=11)
    fig.tight_layout()
    fig.savefig(R / 'section_verified.png', dpi=200)
    plt.close(fig)

    metrics = {}
    all_delta = []
    comparison = {}
    endpoint_notes = []
    model_colors = ['#1464ad', '#1590a6', '#198568']
    manual_colors = ['#d27b12', '#c44442', '#9461aa']
    fig, axs = plt.subplots(3, 2, figsize=(12, 12), sharex=True, sharey=True)
    for row, fn in enumerate(['5.6', '8', '22']):
        ref = np.asarray(target['data'][fn], dtype=float)
        hh = heights_for(target, fn, len(ref))
        extra = target.get('plot_only_additional_points', {}).get(fn)
        if extra:
            for eh, ey in zip(extra['heights'], extra['data']):
                if not np.any(np.isclose(hh, eh, atol=1e-8)):
                    hh = np.r_[hh, float(eh)]
                    ref = np.vstack([ref, np.asarray(ey, dtype=float)])
                    endpoint_notes.append(f'f/{fn} {100*eh:.1f}% 手册附加终点已纳入报告验收。')
            order = np.argsort(hh)
            hh, ref = hh[order], ref[order]
        yy = np.asarray(v['results'][fn], dtype=float)
        vh = heights_for(v, fn, len(yy), hh)
        ch = heights_for(curves, fn, len(curves['results'][fn]))
        cy = np.asarray(curves['results'][fn], dtype=float)
        if ref.shape[1] != 6 or yy.shape[1] != 6 or cy.shape[1] != 6:
            raise ValueError('MTF column order must be 5T,5S,10T,10S,20T,20S')
        if hh.min() < ch.min() - 1e-8 or hh.max() > ch.max() + 1e-8:
            raise ValueError(f'f/{fn}: reference outside complete high-sampling curve grid')
        exact = np.asarray([np.any(np.isclose(vh, h, atol=1e-8)) for h in hh])
        model = np.empty_like(ref)
        for hi, h in enumerate(hh):
            native = np.flatnonzero(np.isclose(vh, h, atol=1e-8))
            model[hi] = yy[native[0]] if len(native) else [np.interp(h, ch, cy[:, j]) for j in range(6)]
        delta = model - ref
        short = np.maximum(-delta, 0)
        idx = np.unravel_index(np.argmax(short), short.shape)
        m = {'rmse': float(np.sqrt(np.mean(delta ** 2))), 'max_shortfall': float(short.max()),
             'minimum_signed_margin': float(delta.min()), 'maximum_signed_margin': float(delta.max()),
             'points_at_or_above_reference': int((delta >= 0).sum()),
             'within_2_percentage_point_lower_bound': int((delta >= -.02).sum()),
             'within_4_percentage_point_lower_bound': int((delta >= -.04).sum()),
             'points': int(delta.size), 'directly_validated_reference_points': int(exact.sum() * 6),
             'interpolated_reference_points': int((~exact).sum() * 6),
             'worst_shortfall_height_fraction': float(hh[idx[0]]),
             'worst_frequency_lp_mm': [5, 10, 20][idx[1] // 2],
             'worst_direction': ['T', 'S'][idx[1] % 2]}
        metrics[fn] = m
        all_delta.extend(delta.ravel())
        comparison[fn] = {'heights': hh.tolist(), 'model': model.tolist(), 'manual': ref.tolist(), 'signed_delta': delta.tolist()}
        for col, direction in enumerate(['S', 'T']):
            ax = axs[row, col]
            j = 1 if direction == 'S' else 0
            style = '-' if direction == 'S' else '--'
            for k, freq in enumerate([5, 10, 20]):
                ax.plot(ch * 100, cy[:, 2 * k + j], linestyle=style, color=model_colors[k], lw=1.8,
                        label=f'Model {freq} lp/mm')
                ax.plot(hh * 100, ref[:, 2 * k + j], linestyle=style, color=manual_colors[k], lw=1.6,
                        label=f'Manual {freq} lp/mm')
            if hh.max() < .999:
                ax.axvspan(hh.max() * 100, 100, color='#b8c0c7', alpha=.12)
            ax.set(xlim=(0, 100), ylim=(0, 1))
            ax.set_title(f'f/{fn} {direction} - {"solid" if direction == "S" else "dashed"}', fontsize=14)
            ax.tick_params(labelsize=12.5)
            ax.grid(alpha=.2)
            handles, labels=ax.get_legend_handles_labels()
            order=[0,2,4,1,3,5]
            ax.legend([handles[k] for k in order],[labels[k] for k in order],ncol=2, fontsize=12.5, loc='lower left', framealpha=.85)
            if col == 0:
                ax.set_ylabel('MTF', fontsize=13)
            if row == 2:
                ax.set_xlabel('Reference image height / 193 mm (%)', fontsize=13)
    fig.suptitle('R3 native FFT MTF: blue/green = simulation; orange/red/purple = manual\nGrey: no published reference. All curves use lines without point markers.', fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, .95))
    fig.savefig(R / 'MTF_full_field.png', dpi=220)
    plt.close(fig)

    reopened_path = R / 'zmx_reopen_verification.json'
    reopened = read(reopened_path) if reopened_path.exists() else []
    image_values = v.get('image_distances_mm', {})
    if isinstance(reopened, list) and len(reopened) == 3:
        image_values = {}
        for item in reopened:
            name = item['file']
            fn = '5.6' if 'f5p6' in name else '22' if 'f22' in name else '8'
            image_values[fn] = float(item['image_distance_mm'])
    if isinstance(image_values, dict) and len(image_values) == 3:
        same_image = max(image_values.values()) - min(image_values.values()) < 1e-7
    elif 'common_image_distance_mm' in v:
        image_values = {fn: v['common_image_distance_mm'] for fn in ['5.6', '8', '22']}
        same_image = True
    else:
        image_values = {fn: sur[-1]['thickness_mm'] for fn in ['5.6', '8', '22']}
        same_image = None
    summary = {'per_aperture': metrics, 'full_field_deg': v['full_field_deg'], 'min_air_gap_mm': min_gap,
               'all_points_at_or_above_reference': bool(np.all(np.asarray(all_delta) >= 0)),
               'all_points_within_2pp_readout_band': bool(np.all(np.asarray(all_delta) >= -.02)),
               'all_points_within_4pp_readout_band': bool(np.all(np.asarray(all_delta) >= -.04)),
               'all_comparisons_directly_validated': all(m['interpolated_reference_points'] == 0 for m in metrics.values()),
               'same_image_plane_verified': same_image, 'image_distances_mm': image_values,
               'manufacturer_readout_uncertainty_mtf': [.02, .04], 'geometry': geometry_output,
               'comparison': comparison, 'audit_file_available': audit is not None,
               'manufacturing_metrics_available': manufacturing is not None,
               'diffraction_reference_available': diffraction is not None,
               'scope': 'Discrete audited reference points, not proof over all continuous field positions.'}
    (R / 'acceptance.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')

    pdfmetrics.registerFont(TTFont('SXL', r'C:\Windows\Fonts\simhei.ttf'))
    styles = {
        'title': ParagraphStyle('title', fontName='SXL', fontSize=20, leading=28, spaceAfter=15, textColor=colors.HexColor('#17384b')),
        'h': ParagraphStyle('h', fontName='SXL', fontSize=13, leading=19, spaceBefore=10, spaceAfter=6, keepWithNext=True, textColor=colors.HexColor('#17384b')),
        'body': ParagraphStyle('body', fontName='SXL', fontSize=9.6, leading=15, spaceAfter=7, wordWrap='CJK'),
        'small': ParagraphStyle('small', fontName='SXL', fontSize=8, leading=12, spaceAfter=4, wordWrap='CJK')}
    md = ['# Super-Symmar XL 150 mm f/5.6 光学性能与制造可能性报告 - R3\n']
    story = []

    def par(txt, style='body'):
        return Paragraph(escape(str(txt)), styles[style])

    def section(title, text):
        story.extend([par(title, 'h'), par(text)])
        md.append(f'## {title}\n\n{text}\n')

    def tab(rows, widths):
        data = [[par(x, 'small') for x in row] for row in rows]
        tb = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
        tb.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e7f0f6')),
                               ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('GRID', (0, 0), (-1, -1), .3, colors.HexColor('#b8c7d0')),
                               ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                               ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
        story.append(tb)
        md.append('| ' + ' | '.join(str(x) for x in rows[0]) + ' |\n| ' + ' | '.join('---' for _ in rows[0]) + ' |\n' + '\n'.join('| ' + ' | '.join(str(x) for x in row) + ' |' for row in rows[1:]) + '\n')

    def num(x, precision=6):
        return '平面' if not np.isfinite(float(x)) else f'{float(x):.{precision}f}'

    def footer(c, d):
        c.setFont('SXL', 8)
        c.setFillColor(colors.HexColor('#77838c'))
        c.drawString(40, 26, 'Super-Symmar XL 150 mm | R3 reverse candidate')
        c.drawRightString(555, 26, str(d.page))

    strict = summary['all_points_at_or_above_reference']
    direct = summary['all_comparisons_directly_validated']
    outcome = ('本次审核的离散对照点均达到或超过重新量读的原厂 MTF。' if strict else '本次审核仍有离散对照点低于重新量读的原厂 MTF，尚未满足全点达到或超过的目标。')
    if not direct:
        outcome += ' 部分对照值由高采样结果沿视场插值，不能表述为全部对照点均经直接复算。'
    outcome += (' 受检光学表面区域未发现交叠。' if no_overlap else ' 几何检查发现非正间隙或厚度，不能进行制造放行。')
    story.append(Paragraph('光学性能与制造可能性报告<br/>Super-Symmar XL 150 mm f/5.6 - R3', styles['title']))
    section('结论与判定边界', outcome + ' 下表为原生 FFT 结果；Huygens 交叉计算尚未收敛，计算适用性仍有待验证。原厂扫描图人工读数的不确定度约为 2-4 个百分点；严格达到读数、在读图误差带内相容，以及连续全视场都优于原厂，是不同的判断。本报告不将后两者替代严格离散点判定，也不承诺量产性能。')
    tab([['光圈', '最大低于原厂\n百分点', '严格达到下限\n样点数', '不足不超过 4 点\n样点数'], *[[f'f/{fn}', f"{100*m['max_shortfall']:.2f}", f"{m['points_at_or_above_reference']} / {m['points']}", f"{m['within_4_percentage_point_lower_bound']} / {m['points']}"] for fn, m in metrics.items()]], [65, 140, 145, 165])
    section('手册重新审核', '上一轮手册读数审核发现实质性偏差，本轮使用 target_dense_audited.json 重新量读的密集数据及其 target_optimization.json 副本，不沿用旧版目标数值作优劣结论。图中的橙、红、紫色线是人工数字化读数连接而成的折线，不是原厂原始采样数据；蓝、青、绿色线是模拟结果。未公开参考线的视场不推定原厂 MTF 为零。')
    if endpoint_notes:
        section('公开曲线终点', ' '.join(endpoint_notes) + ' 若该点没有最终直接复算记录，验收统计使用完整视场高采样曲线插值并明确披露，不因初期优化目标文件遗漏而排除。')
    section('审核数据说明', '手册数据由用户提供的 PDF 第 2 页无限远物距一行重新量读，保留原始扫描图和旧读数用于追溯。数值为近似人工数字化结果，并非原厂公开的数值表。f/8 的 78% 终点已纳入本轮直接复算和验收。')
    section('模型与共同模拟条件', f"无限远物距、平面像面；全部光圈均保留 {v['full_field_deg']:.1f}° 全视场，最大半视场 {max(v['field_angles_deg']):.4f}°。采用原厂 546、644、588、480、436、405 nm，权重 24.6、18.6、22.1、12.4、15.2、7.1%。MTF 比较采用 5、10、20 lp/mm；列次序为 T、S，S 实线、T 虚线。光阑半口径解算：{v.get('stop_solve', '未记录')}。")
    plane = ('三文件同像面已由验证数据明确记录。' if same_image else '验证数据尚未明确记录三文件同像面重读证明。' if same_image is None else '三档光圈像面不一致，比较条件不合格。')
    section('统一像面', f"本报告不为不同光圈分别移动像面。末面到像面名义距离为 {sur[-1]['thickness_mm']:.8f} mm。{plane} 三档记录：" + '；'.join(f'f/{fn}: {dist:.8f} mm' for fn, dist in image_values.items()) + '。原厂聚焦程序的完全等效性仍须由实际验证流程确认，不能仅凭焦距与像距接近推断。')

    section('采样收敛与误差', '收敛表比较同一处方、同一聚焦条件下的最终高采样与 256 采样。该差异检查数值稳定性，不代表制造公差、原厂读图精度或实物 MTF。定量验收使用 validated.json，完整视场曲线使用 field_curves.json。')
    story.extend([PageBreak(), par('FFT 模拟 MTF 与手册 MTF 对比', 'h'), Image(str(R / 'MTF_full_field.png'), width=515, height=515)])
    md.append('## 模拟 MTF 与手册 MTF 对比\n\n![MTF](MTF_full_field.png)\n')
    section('图线与视场说明', '每行分别为 f/5.6、f/8、f/22，每列分别为 S、T 方向。各小图图例同时列出模拟和手册的三种频率；全部曲线不使用圈、叉或任何点标记。横坐标以手册最大像高 193 mm 归一化，灰色区仅表示该光圈没有公开的参考曲线，不改变模型最大视场。手册折线之间的细节不能视为已经公开的连续原厂曲线。')
    tab([['光圈', '高采样', '相对 256 最大变化\n百分点', '最大不足的位置'], *[[f'f/{fn}', str(v.get('sampling', {}).get(fn, '未记录')), f"{100*v['convergence_from_256'][fn]:.3f}" if fn in v.get('convergence_from_256', {}) else '未记录', f"{100*m['worst_shortfall_height_fraction']:.1f}% / {m['worst_frequency_lp_mm']} lp/mm {m['worst_direction']}"] for fn, m in metrics.items()]], [60, 90, 145, 220])

    story.extend([PageBreak(), par('结构与几何可行性', 'h'), Image(str(R / 'section_verified.png'), width=515, height=230)])
    md.append('## 结构与几何可行性\n\n![结构](section_verified.png)\n')
    section('手册结构图的作用', f"手册右上结构图与专利第一实施例轴上顶点共同定标的比例约 {dc['scale_pixels_per_mm']:.3f} 像素/mm，轴向残差 RMS 约 {dc['axial_residual_rms_mm']:.3f} mm。此结果支持该图作为光学布局与有效口径的参考，但人工读图不是实物计量，也不是生产尺寸公差。口径读图不确定度约 ±0.3 mm。")
    tab([['空气间隙', '检查半径 mm', '最小间隙 mm'], *[[f"S{g['after_surface']} - S{g['before_surface']}", f"{g['checked_radius_mm']:.3f}", f"{g['min_gap_mm']:.5f}"] for g in geometry]], [125, 180, 210])
    section('最后两片的保守检查', f"对 S10 非球面与 S11 末片前球面，保守将球面延伸至 S10 的通光半径再增加 0.3 mm 读图余量，检查结果最小空气间隙为 {geometry[-1]['min_gap_mm']:.5f} mm。全部受检空气间隙最小值为 {min_gap:.5f} mm。另检查六片玻璃在共同有效口径内的局部厚度。以上是名义光学面几何检查，未包含压圈、倒角、胶层、装配偏心与温度误差；不能当作装配间隙的公差保证。结构图中的直线边缘连接仅为示意。")
    story.append(Image(str(P / 'revision2' / 'reference_section.png'), width=225, height=184))
    story.append(par('来源：所提供 super-symmar_xl_56_150.pdf 第 1 页右上结构图。', 'small'))

    story.extend([PageBreak(), par('完整光学处方与非球面', 'h')])
    section('单位与面号', '长度单位为 mm，曲率半径正负采用 Zemax 顺序追迹约定。厚度表示到下一面沿轴距离；S12 的厚度为末面到统一像面距离。玻璃名称表示该面之后介质，空白为空气；S7 为独立光阑面。本表包含全部 12 面，不包含无限远物面与像面。')
    tab([['面', '曲率半径 mm', '到下一面 mm', '玻璃', '通光半径 mm'], *[[str(s['surface']) + (' 光阑' if s.get('stop') else ''), num(s['radius_mm']), num(s['thickness_mm']), s['glass'] or '空气', num(s['clear_radius_mm'], 4)] for s in sur]], [55, 120, 125, 105, 110])
    section('S10 偶次非球面', f'z(r) = c*r^2/[1+sqrt(1-(1+k)*c^2*r^2)] + sum(Ap*r^p)，其中 c=1/R，p 为 4、6、8 至 {int(powers[-1])} 的偶数。系数采用 mm 单位，必须与曲率半径共同使用，不能解释为面形误差公差。光阑行是 f/5.6 时的自动半口径，其它光圈由原生模型自动解算。')
    tab([['参数', 'R3 最终数值', '单位'], ['圆锥常数 k', str(sur[9].get('conic', v.get('asphere_conic', 0))), '无量纲'], *[[f'A{power}', f'{a:.12e}', f'mm^({1-power})'] for a, power in zip(coef, powers)]], [80, 290, 145])

    story.extend([PageBreak(), par('相对于 R2 的变化与制造评估', 'h')])
    changed = []
    for s, previous in zip(sur, old['surfaces']):
        fields = []
        for key, label in [('radius_mm', 'R'), ('thickness_mm', '间隔'), ('clear_radius_mm', '口径半径')]:
            a, b = float(s[key]), float(previous[key])
            if np.isfinite(a) and np.isfinite(b) and abs(a - b) > 1e-8:
                fields.append(f'{label} {a-b:+.6f} mm')
        if s['glass'] != previous['glass']:
            fields.append(f"玻璃 {previous['glass'] or '空气'} -> {s['glass'] or '空气'}")
        if fields:
            changed.append([f"S{s['surface']}", '；'.join(fields)])
    section('结构变化按最终数据统计', '以下变化由最终 R3 与 R2 的 validated.json 逐面比较得出，不假设本轮实际使用了哪组优化变量或限制。未列出的对应数值在 1e-8 mm 比较阈值内一致。S12 间隔变化表示共同像面的变化，不是镜片中心厚度。')
    tab([['面号', 'R3 - R2'], *(changed or [['全部面', '处方表中的曲率、间隔、口径与玻璃未检出变化']])], [70, 445])
    section('非球面与一阶参数变化', f'A4-A{int(powers[-1])} 系数相对 R2 的差值依次为：' + '；'.join(f'{a-b:+.6e}' for a, b in zip(coef, old_coef)) + '。若 R2 没有 A14/A16，则以零项比较。本轮有效焦距为 ' + f"{v['first_order']['EFFL']:.6f} mm，入瞳位置为 {v['first_order']['ENPP']:.6f} mm，首面到末面的轴向长度为 {z[-1]:.6f} mm。原厂公开对应值约为 148.1、36.6、77.4 mm；参数接近不代表完整处方已被唯一恢复。")
    section('材料采购与加工', '处方中玻璃是完整色散目录候选，其名称和在 Zemax 中存在不等于已确认现货或毛坯可用。应取得供应商实际熔次色散、均匀性、退火、尺寸和环境稳定性数据；更换玻璃需在全波段重新优化。胶合组外非球面需要加工、定心与独立面形检测方案，明确有效口径、基准球、边缘余厚、胶层及倒角后才可询价。')
    section('制造可能性的当前结论', outcome + ' 即使理想 MTF 达到原厂，也只是名义设计结果。本轮没有曲率、厚度、间距、偏心、倾斜、非球面误差、胶层、装配补偿和温度的完整公差分析，没有 Monte Carlo 良率或样机实测。因此可以继续设计评估，不能据此声明直接量产、生产良率、成本或交期。')

    story.extend([PageBreak(), par('非球面加工描述与镜片厚度检查', 'h')])
    if manufacturing is None:
        section('制造几何描述未核验', '没有 manufacturing_geometry_metrics.json，尚未核验本次最终处方的非球面离开量、表面斜率、共同有效口径内的镜片边缘厚度。前文表面间隙检查不能替代这些制造几何指标。')
    else:
        a = manufacturing['asphere']
        stored = np.asarray(a['coefficients'], dtype=float)
        coefficients_match = len(stored) == len(coef) and np.allclose(stored, coef, rtol=1e-8, atol=0)
        radius_match = abs(a['prescribed_vertex_radius_mm'] - sur[9]['radius_mm']) < 1e-7
        if not coefficients_match or not radius_match:
            section('制造指标与最终输入不一致', '现有 manufacturing_geometry_metrics.json 的系数或顶点曲率与本次 validated.json 不一致，不能作为本次最终处方的制造几何证明。必须重新运行 manufacturing_metrics_revision3.py；本报告不引用其旧非球面数值。')
        else:
            section('非球面离开量与斜率', f"S10 有效半径 {a['clear_radius_mm']:.3f} mm；参考为处方指定顶点半径球面，不是拟合最佳球面。设计离开量范围 {a['departure_min_um']:.3f} 至 {a['departure_max_um']:.3f} μm，PV {a['departure_pv_um']:.3f} μm；最大绝对表面斜率 {a['maximum_absolute_surface_slope_mm_per_mm']['value']:.6f} mm/mm，最大绝对斜率离开量 {a['maximum_absolute_slope_departure_mm_per_mm']['value']:.6f} mm/mm；最大绝对表面倾角 {a['maximum_absolute_surface_angle_deg']['value']:.4f}°。这些是设计面形及斜率，不能称为要求工厂达到的误差公差。")
            profile = R / 'asphere_profile.png'
            if profile.exists():
                story.append(Image(str(profile), width=515, height=328))
                md.append('![非球面设计轮廓](asphere_profile.png)\n')
            else:
                section('轮廓图缺失', 'asphere_profile.png 尚未生成；以上仅引用已存在的制造几何数值。')
            tab([['镜片 / 玻璃', '中心厚度 mm', '共同口径边缘厚度 mm', '受检最薄处 mm'], *[[f"L{e['element']} / {e['glass']}", f"{e['center_thickness_mm']:.5f}", f"{e['edge_thickness_mm']:.5f}", f"{e['minimum_thickness_mm']:.5f}"] for e in manufacturing['glass_elements']]], [145, 110, 145, 115])
            section('厚度检查范围', f"采用 {manufacturing['radial_sample_count']} 个均匀径向样点，曲面导数按储存的圆锥加偶次多项式解析计算。镜片厚度只覆盖前后光学面的共同有效口径，未定义的倒角和机械外缘不在检查域内。制造指标中的保守后组间隙为 {manufacturing['rear_gap_conservative_extension']['minimum_gap_mm']:.5f} mm；这也不是带公差的装配最小间隙。")

    story.extend([PageBreak(), par('实际像高、瞳面与原厂聚焦审核', 'h')])
    if audit is None:
        section('原生光线与聚焦审核未核验', '没有 mapping_pupil_focus_audit.json，不能确认最终处方的实际主光线像高、机械口径对入瞳的遮挡、原生相对照度，或 f/5.6 轴上 20 lp/mm 达到最大值的聚焦条件。前文离散 MTF 统计不构成这些条件已核验的证明。')
    else:
        section('审核文件与方法', f"原生审核模型：{Path(audit['model']).name}。审核的末面像距 {audit['official_image_distance_mm']:.8f} mm；入瞳单位圆每波长 {audit['grid_samples_per_wavelength']} 个均匀笛卡尔网格射线，{audit['wavelength_count']} 个波长。主光线使用原生真实光线并与 REAY 交叉检查。审核不保存或改写交付 ZMX。")
        if abs(audit['official_image_distance_mm'] - sur[-1]['thickness_mm']) > 1e-7:
            section('审核像距与最终输入不同', '审核记录与最终 validated.json 的像距不一致，不能确认审核属于本次最终版本。必须重跑该审核后才能将以下数值作为最终模型证明。')
        rows = [['光圈', '公开对照场最大映射偏差 mm', '公开对照场最大相对畸变 %', '轴上 / 全场边缘几何瞳份额 %']]
        for fn in ['5.6', '8', '22']:
            fields = audit['apertures'][fn]['fields']
            published = [x for x in fields if x.get('is_published_reference_height_for_aperture')]
            if not published:
                published = fields
            off_axis = [x for x in published if x['reference_height_fraction'] > 0]
            deviation = max(abs(x['height_mapping_error_mm']) for x in published)
            distortion = max([abs(x['distortion_relative_to_reference_pct']) for x in off_axis] or [0])
            axis = min(fields, key=lambda x: x['reference_height_fraction'])
            edge = max(fields, key=lambda x: x['reference_height_fraction'])
            rows.append([f'f/{fn}', f'{deviation:.5f}', f'{distortion:.4f}', f"{100*axis['weighted_geometric_pupil_fraction']:.2f} / {100*edge['weighted_geometric_pupil_fraction']:.2f}"])
        tab(rows, [55, 150, 150, 160])
        section('像高映射的判定', '表中偏差为实际主波长主光线像面 y 与 193h mm 的差，相对畸变为该差除以 193h。已有审核证明映射偏差的数值，尚不自动证明 MTF 已按相同实际像高重采样或重新优化；有明显偏差时，严格与手册比较应按真实像高重新指定视场。主光线的错误码、遮挡码及多波长记录保留在审核 JSON 中。')
        section('瞳面与照度的区别', '几何瞳份额是单位圆网格中错误码和遮挡码均为零的射线比例，按六波长权重汇总；它不等于照度、透射率或生产良率。边缘值覆盖完整系统视场，可能超出某光圈的手册 MTF 公开范围。MTF 归一化后可与很低的通光份额同时存在，因此不能仅凭 MTF 提升推断通光性能提高。')
        illumination_rows = [['光圈', '原生相对照度审核']]
        for fn in ['5.6', '8', '22']:
            ri = audit['apertures'][fn].get('native_relative_illumination')
            series = ri.get('series', []) if ri else []
            samples = [float(row[0]) for row in series[0]['y'] if row] if series else []
            illumination_rows.append([f'f/{fn}', f"首列相对照度：轴上 {samples[0]:.6f}，扫描终点 {samples[-1]:.6f}；范围 {min(samples):.6f} 至 {max(samples):.6f}" if samples else '无有效数据序列，尚未确认原生照度结果'])
        tab(illumination_rows, [55, 460])
        section('原生照度数据列', '原生照度结果 Y 数据第一列为相对照度，第二列为工作 f 数。本表仅引用第一列，未把工作 f 数混入照度统计；端点是原生扫描的最后一个样点，具体扫描坐标保留在审核 JSON。几何瞳份额与该照度结果保持独立。')
        focus = audit.get('focus_scan')
        if focus:
            best, official = focus['best_grid_sample'], focus['official_plane_mtf']
            gain = best['mean_axis_20_mtf'] - official['mean_axis_20_mtf']
            focus_status = ('正式像面与扫描最佳样点重合，满足本次有限网格局部扫描的原厂轴上最大化检查。' if abs(best['image_distance_offset_mm']) < 1e-8 else '正式像面并非此扫描最佳点，仍未严格满足原厂聚焦条件。')
            section('原厂聚焦规则的扫描检查', f"按 f/5.6、轴上 20 lp/mm、{focus['sampling']} 采样扫描统一像面。正式像面平均 T/S MTF 为 {official['mean_axis_20_mtf']:.6f}；扫描最佳样点位于正式像面 {best['image_distance_offset_mm']:+.6f} mm，MTF {best['mean_axis_20_mtf']:.6f}，增益 {100*gain:.4f} 个百分点。最佳点{'位于扫描边界，必须扩展扫描才能判断最大值。' if focus['peak_at_scan_boundary'] else '位于扫描内部；这是有限网格局部扫描，不能直接证明全局最佳聚焦。'} {focus_status}")
        else:
            section('聚焦审核缺失', '审核文件没有 focus_scan，尚未核验原厂轴上 20 lp/mm 最大化条件。')
        for warning in audit.get('warnings', []):
            story.append(par('审核提示：' + str(warning)[:800], 'small'))

    story.extend([PageBreak(), par('本轮改善与独立计算检查', 'h')])
    baseline_path = R / 'R2_same_condition_baseline.json'
    if baseline_path.exists():
        baseline = read(baseline_path)
        section('采用同一手册读数的 R2 对照', 'R2 按本轮 186 项手册目标、原厂六波长、固定通光口径和 f/5.6 轴上 20 lp/mm 最大化规则重新聚焦复算；三档光圈使用共同像面。下表比较最大不足，数值越小越好；R2 使用 256 采样，本轮使用前文最终高采样，因此不将末位小差异解释为确定的设计增益。最大不足定义为 max(手册 MTF - 模拟 MTF, 0)。')
        tab([['光圈', '同条件 R2 最大不足\n百分点', '本轮最大不足\n百分点'], *[[f'f/{fn}', f"{100*baseline['per_aperture'][fn]['max_shortfall']:.3f}", f"{100*metrics[fn]['max_shortfall']:.3f}"] for fn in ['5.6', '8', '22']]], [70, 220, 225])
        section('改善的限度', '最大不足降低只表明该光圈的最差下限差距缩小，不能推导每一条曲线、每一个视场都比 R2 或原厂更好。前文逐点有符号差和最终共同像面记录仍是本次判定依据。')
    else:
        section('同条件基线缺失', '没有 R2_same_condition_baseline.json，不能用旧目标文件的 R2 数字直接宣称本轮改善。')
    hp = R / 'huygens_validation.json'
    if hp.exists():
        hv = read(hp)
        attached_checks=hv.get('fixed_window_checks', {})
        fixed_pupil_path=R/'huygens_pupil256_fixed_window.json'
        if fixed_pupil_path.exists():
            hv=read(fixed_pupil_path)
            hv['fixed_window_checks']=attached_checks
        section('Huygens 与 FFT 的独立交叉检查', '宽角度系统的出瞳分布或截瞳可能影响 FFT 假设。下表引用原生 Huygens 与 FFT 在同一候选、同一像面和相同光谱条件下的计算；不因增加 FFT 采样就自动认为这些假设已经成立。')
        hrs = [row for row in hv.get('rows', []) if row.get('frequency_lp_mm') == 20]
        if hrs:
            best_sampling=max(row['pupil_sampling'] for row in hrs)
            hrs=[row for row in hrs if row['pupil_sampling']==best_sampling]
        if abs(hv.get('common_image_distance_mm', -1)-sur[-1]['thickness_mm'])>1e-7:
            section('交叉检查版本不一致', 'Huygens 审核的像面与本次最终处方不同；以下数值不能作为交付版本的有效性证明。')
        if hrs:
            tab([['光圈 / h', 'Huygens 瞳/像采样', 'FFT T / S', 'Huygens T / S'], *[[f"f/{row['aperture']} / {row['height']:.2f}", f"{row['pupil_sampling']} / {row['image_sampling']}", f"{row['FFT_T']:.4f} / {row['FFT_S']:.4f}", f"{row['Huygens_T']:.4f} / {row['Huygens_S']:.4f}"] for row in hrs]], [90, 115, 155, 155])
        else:
            section('交叉检查未完成', '审核文件没有有效的 20 lp/mm 对照记录，不能确认宽角度 FFT 结果的独立有效性。')
        settings=hv.get('settings', {})
        section('Huygens 设置与收敛边界', f"像面网格 {settings.get('image_sampling', '未记录')}；ImageDelta={settings.get('image_delta', '未记录')} μm（0 表示原生自动间距）。表中采用最高已完成的瞳面采样，全部初审记录保存在 JSON 中。Huygens 也需要检验像面间距与计算窗口的收敛；本次初审不自动构成该收敛已通过的证明。")
        failures=hv.get('failures', [])
        if failures:
            section('交叉检查计算异常', f'有 {len(failures)} 项计算未返回可用结果，详见审核 JSON 和原生文本。')
        row_warnings=[warning for row in hrs for warning in row.get('warnings', [])]
        if row_warnings:
            section('原生数值警告', '部分计算返回警告或超出正常 MTF 范围，不接受为可靠的性能证明；详见原生审核文本。')
        checks=hv.get('fixed_window_checks', {})
        if checks:
            wc=checks.get('fixed_1um_axis_image512_to1024_max_absolute_change')
            pc=checks.get('fixed_1um_image512_axis_pupil128_to256_max_absolute_change')
            parts=[]
            if wc is not None:parts.append(f'固定 1 μm 间距、瞳采样 128，像面 512 到 1024 的最大变化 {100*wc:.4f} 个百分点')
            if pc is not None:parts.append(f'固定 512 像面和 1 μm 间距，瞳面 128 到 256 的最大变化 {100*pc:.4f} 个百分点')
            full_control_path=R/'huygens_full_fixed_window.json'
            if full_control_path.exists():
                full_control=read(full_control_path)
                for record in hv.get('results', []):
                    if record['f_number']=='5.6' and record['reference_height_fraction']==.6 and '256' in record['samples']:
                        before=next((c for c in full_control['cases'] if c['aperture']=='5.6' and c['height']==.6 and c['image_distance_offset_mm']==0),None)
                        if before:
                            after=record['samples']['256']['Huygens']['values_5T_5S_10T_10S_20T_20S']
                            change=float(np.max(abs(np.array(after)-before['values_5T_5S_10T_10S_20T_20S'])))
                            difference=record['samples']['256']['maximum_absolute_difference']
                            parts.append(f'h=0.6 瞳面 128 到 256 最大变化 {100*change:.4f} 个百分点；256 Huygens 与 FFT 最大差 {100*difference:.4f} 个百分点')
            section('分别核对窗口与瞳面', '；'.join(parts)+'。窗口变化小不代表瞳面积分收敛，不能用偏高的初审 MTF 宣称优于原厂。')
    else:
        section('Huygens 尚未完成', '尚无 huygens_validation.json；FFT 高采样收敛不构成对宽角度出瞳假设的独立验证。')
    story.append(Paragraph('方向定义来源：<link href="https://schneiderkreuznach.com/en/industrial-optics/knowledge-hub/modulation-transfer-function" color="#24628a">施耐德 MTF 说明</link>（T 虚线、S 实线）。计算假设来源：<link href="https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v252/en/OpticStudio_User_Guide/OpticStudio_Help/topics/FFT_MTF.html" color="#24628a">Ansys FFT MTF 文档</link>（2025 R2 文档；本机计算版本为 2023 R1）。', styles['small']))
    md.append('方向定义：[施耐德 MTF 说明](https://schneiderkreuznach.com/en/industrial-optics/knowledge-hub/modulation-transfer-function)。计算假设：[Ansys FFT MTF 文档](https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v252/en/OpticStudio_User_Guide/OpticStudio_Help/topics/FFT_MTF.html)。\n')
    full_hp=R/'huygens_full_fixed_window.json'
    if full_hp.exists():
        full_h=read(full_hp)
        if full_h.get('completed') and not full_h.get('failures'):
            hmetrics={}
            fig,axs=plt.subplots(3,2,figsize=(12,12))
            for row,fn in enumerate(['5.6','8','22']):
                actual=sorted([c for c in full_h['cases'] if c['aperture']==fn and c['image_distance_offset_mm']==0],key=lambda c:c['height'])
                hh=np.array([c['height'] for c in actual]);hy=np.array([c['values_5T_5S_10T_10S_20T_20S'] for c in actual]);ref=np.array(target['data'][fn]);th=np.array(target['heights_by_aperture'][fn])
                assert np.allclose(hh,th)
                hmetrics[fn]=float(np.maximum(ref-hy,0).max())
                for col,direction in enumerate(['S','T']):
                    ax=axs[row,col];j=1 if direction=='S' else 0;ls='-' if j else '--'
                    for k,freq in enumerate([5,10,20]):
                        ax.plot(hh*100,hy[:,2*k+j],ls=ls,color=model_colors[k],lw=1.8,label=f'Huygens {freq} lp/mm')
                        ax.plot(th*100,ref[:,2*k+j],ls=ls,color=manual_colors[k],lw=1.6,label=f'Manual {freq} lp/mm')
                    ax.set(xlim=(0,100),ylim=(0,1),title=f'f/{fn} {direction}')
                    ax.tick_params(labelsize=12.5);ax.grid(alpha=.2)
                    handles,labels=ax.get_legend_handles_labels();order=[0,2,4,1,3,5]
                    ax.legend([handles[k] for k in order],[labels[k] for k in order],ncol=2,fontsize=12,loc='lower left',framealpha=.85)
                    if col==0:ax.set_ylabel('MTF',fontsize=13)
                    if row==2:ax.set_xlabel('Reference image height / 193 mm (%)',fontsize=13)
            fig.suptitle('Huygens preliminary: pupil 128 / image 512 / 1 um\nPupil integration is NOT converged. Lines connect calculated reference knots.',fontsize=14)
            fig.tight_layout(rect=(0,0,1,.95));fig.savefig(R/'Huygens_reference_comparison.png',dpi=220);plt.close(fig)
            story.extend([PageBreak(),par('固定窗口 Huygens 手册场点初审 — 未收敛','h'),Image(str(R/'Huygens_reference_comparison.png'),width=515,height=515)])
            tab([['光圈','初审最大不足，百分点','协议'],*[[f'f/{fn}',f'{100*hmetrics[fn]:.3f}','瞳128 / 像512 / 间距1 μm'] for fn in ['5.6','8','22']]], [70,180,265])
            section('禁止把初审用于性能放行','31 个手册场点共 186 项初审均由原生 Huygens 在正式共同像面计算，未公开范围不作外推。瞳面积分仍未收敛，此图展示计算方法差异，不能替代前文 FFT 数据或证明模型达到原厂。本轮没有据此重设正式像面。')
            md.append('![Huygens 未收敛初审](Huygens_reference_comparison.png)\n')
    story.extend([PageBreak(), par('衍射参考与验证边界', 'h')])
    if diffraction is None:
        section('衍射参考未核验', '没有 diffraction_reference.json，本报告不提供未经计算的理想圆瞳衍射参考值。')
    else:
        section('衍射参考的含义', '采用原厂六波长权重计算无像差、无遮拦圆形瞳孔的非相干衍射 MTF，归一化空间频率为波长(mm) × f数 × lp/mm。这是指定圆瞳形状的轴上参考，不是适用于任意离轴截瞳、渐晕或瞳面加权系统的通用严格上限，不能把本模型离轴 MTF 高于某项圆瞳值直接认定为计算错误。')
        tab([['光圈', '5 lp/mm', '10 lp/mm', '20 lp/mm'], *[[f'f/{fn}', *[f'{value:.6f}' for value in diffraction['results'][fn]['mtf']]] for fn in ['5.6', '8', '22']]], [65, 150, 150, 150])
        section('性能余量与制造', '尤其在 f/22，原厂轴上曲线已经接近该圆瞳衍射参考，进一步提高理想设计的可用余量较小。制造公差会消耗名义性能余量；本轮不从衍射参考推导任何加工公差、良率或最终实物性能。')

    story.append(par('验证记录、来源与下一步', 'h'))
    section('验证范围', '本报告对最终输入数据进行独立几何和 MTF 下限统计，不自行重跑光学优化。acceptance.json 保存每光圈的最大短缺、严格达标数量、2/4 点读图带数量、直接复算与插值点数、共同像面记录，以及逐点有符号差。geometry_verified.json 保存受检口径与名义间隙。仅有离散点达标时，不将结果扩展为整个连续场域必然优于手册。')
    section('严格比较尚需区分的事项', 'Angle 视场、真实像高、原厂聚焦和归一化 MTF 是不同的条件。审核记录存在时，本报告引用其实际结果；条件未完成时明确保留缺口，不因离散曲线改善而声称所有光学性能均优于原厂。即使一个局部聚焦扫描最佳，也需同像面验证其它光圈并复查高采样收敛。')
    section('完成目标仍需的工作', ('本轮应继续检查离散点之间的最小 MTF 裕量，并把理想性能余量转化为制造公差。' if strict else '应继续修正最大不足所在视场的处方，并同时检查其它光圈和方向，避免通过牺牲某些曲线获得局部改进。') + ' 随后冻结共同聚焦程序、机械有效口径、完整遮挡与装配结构；开展有补偿的公差分析、透射与照度、畸变和有限倍率验证；最后通过样机测量确认性能和生产可行性。')
    section('复算数据与文件', 'revision3/validated.json：最终高采样离散 MTF、处方与一阶数据。revision3/field_curves.json：完整视场模拟曲线。revision3/target_dense_audited.json：本轮重新审核的密集手册数字化读数；target_optimization.json：本轮正式目标副本。revision2/validated.json：上一轮处方。revision2/drawing_constraints.json：结构图定标记录。全部产出保存在 SuperSymmarXL 文件夹中。')
    section('原始资料', '用户提供的 super-symmar_xl_56_150.pdf：公开性能、光谱权重、视场及结构示意。用户提供的 US5870234 Super Symmar XL patent.pdf：结构与专利实施例参考。公开数据不足以唯一恢复原厂实际处方、非球面、制造尺寸及公差；本报告的 ZMX 是可复算的逆向候选，不是经过原厂认证的生产处方。')
    name = '光学性能与制造可能性报告_R3'
    SimpleDocTemplate(str(R / (name + '.pdf')), pagesize=(595, 842), leftMargin=40, rightMargin=40,
                      topMargin=38, bottomMargin=42).build(story, onFirstPage=footer, onLaterPages=footer)
    (R / (name + '.md')).write_text('\n'.join(md), encoding='utf-8')
    print(json.dumps({k: x for k, x in summary.items() if k not in ['comparison', 'geometry']}, indent=2))


if __name__ == '__main__':
    main()
