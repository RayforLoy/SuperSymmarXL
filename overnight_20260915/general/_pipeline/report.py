"""Build the single GENERAL report after final Zemax validation.

Run only after the PDF artifact-operation marker has succeeded. This script does
not connect to Zemax, optimize, or substitute a nominal result for measured data.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import json
import hashlib
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

P = Path('D:\\_Camera\\LensRebuild\\SuperSymmarXL')
R = Path('D:\\_Camera\\LensRebuild\\SuperSymmarXL\\overnight_20260915\\general')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def source_hash(obj):
    if not isinstance(obj, dict):
        return None
    value = obj.get('source_sha256')
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdefABCDEF' for c in value):
        return None
    return value.lower()


def surface_signature(surfaces):
    return [{'surface': int(s['surface']), 'radius_mm': float(s['radius_mm']),
             'thickness_mm': float(s['thickness_mm']), 'glass': str(s['glass']),
             'clear_radius_mm': float(s['clear_radius_mm']),
             'mechanical_radius_mm': float(s['mechanical_radius_mm']),
             'stop': bool(s['stop']), 'conic': float(s['conic'])}
            for s in sorted(surfaces, key=lambda row: int(row['surface']))]


def optional_current(path, expected_hash):
    if not path.exists():
        return None, '文件不存在。'
    try:
        obj = read(path)
    except (OSError, ValueError) as exc:
        return None, '文件不可读取：' + str(exc)
    if not isinstance(obj, dict) or source_hash(obj) != expected_hash:
        return None, 'source_sha256 缺失、无效或与最终冻结处方不一致；不引用该文件任何数值。'
    return obj, None


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


def huygens_spot_summary(v, curves):
    """Require current A6 seed identity and identical fixed-window protocols.

    This is a two-level pupil-sampling spot check, never a convergence pass.
    Historical R3 Huygens files are deliberately not searched or loaded.
    """
    paths = [R / f'huygens_spot_p{size}.json' for size in [128, 256]]
    threshold = float(v.get('huygens_spot_convergence_threshold_mtf', .01))
    result = {'status': 'not_present', 'screening_threshold_mtf': threshold,
              'pupil_convergence_demonstrated': False, 'rows': [], 'reasons': []}
    if not all(path.exists() for path in paths):
        result['reasons'].append('两份本轮 A6 spot 文件尚未齐全。')
        return result
    try:
        protocols = [read(path) for path in paths]
    except (ValueError, OSError) as exc:
        result['status'] = 'not_ready'
        result['reasons'].append('spot JSON 尚不可读取：' + str(exc))
        return result
    candidate = v.get('source_candidate')
    expected_model = (R / candidate).resolve() if candidate else None
    requested = [('5.6', 0.), ('5.6', .6), ('8', .4), ('22', 0.), ('22', .8)]
    indexed = []
    for protocol, size in zip(protocols, [128, 256]):
        if source_hash(v) is None or source_hash(protocol) != source_hash(v):
            result['reasons'].append(f'pupil {size} 的 source_sha256 缺失、无效或与最终冻结处方不一致；不引用数值。')
            indexed.append({})
            continue
        if not protocol.get('completed') or protocol.get('failures'):
            result['reasons'].append(f'pupil {size} 未完成或存在计算失败。')
        model = protocol.get('model')
        if expected_model is None or not model or str(Path(model).resolve()).casefold() != str(expected_model).casefold():
            result['reasons'].append(f'pupil {size} 的模型与最终 source_candidate 不一致或未提供身份记录。')
        if protocol.get('pupil_sampling') != size or protocol.get('image_sampling') != 512 or protocol.get('image_delta_um') != 1:
            result['reasons'].append(f'pupil {size} 的采样或固定 1 μm 窗口设置不符。')
        focus = protocol.get('common_image_distance_mm', protocol.get('official_image_distance_mm'))
        if focus is not None and abs(float(focus) - v['surfaces'][-1]['thickness_mm']) > 1e-7:
            result['reasons'].append(f'pupil {size} 的像距与最终共同像面不一致。')
        entries = {}
        for case in protocol.get('cases', []):
            if abs(float(case.get('image_distance_offset_mm', 0))) > 1e-8:
                continue
            actual_focus = case.get('actual_image_distance_mm', case.get('official_image_distance_mm'))
            if actual_focus is not None and abs(float(actual_focus) - v['surfaces'][-1]['thickness_mm']) > 1e-7:
                result['reasons'].append(f'pupil {size} 的零偏移场点实际像距与最终共同像面不一致。')
            key = (format(float(case['aperture']), 'g'), round(float(case['height']), 10))
            values = np.asarray(case.get('values_5T_5S_10T_10S_20T_20S', []), dtype=float)
            if values.shape != (6,) or not np.all(np.isfinite(values)) or np.any(values < 0) or np.any(values > 1.00001):
                result['reasons'].append(f'pupil {size} 场点 {key} 没有合法的六项 MTF。')
                continue
            if key in entries:
                result['reasons'].append(f'pupil {size} 场点 {key} 记录重复。')
            entries[key] = values
        if any(key not in entries for key in requested):
            result['reasons'].append(f'pupil {size} 未包含要求的全部五个零像距偏移场点。')
        indexed.append(entries)
    if curves.get('sampling') != 512:
        result['reasons'].append('本轮 FFT 完整视场曲线未记录为 512 采样。')
    if result['reasons']:
        result['status'] = 'not_ready'
        return result
    for fn, height in requested:
        hh = heights_for(curves, fn, len(curves['results'][fn]))
        yy = np.asarray(curves['results'][fn], dtype=float)
        if height < hh.min() or height > hh.max():
            result['reasons'].append(f'f/{fn} h={height} 超出当前 FFT512 曲线域。')
            continue
        fft = np.asarray([np.interp(height, hh, yy[:, j]) for j in range(6)])
        lo, hi = indexed[0][(fn, height)], indexed[1][(fn, height)]
        delta = np.abs(hi - lo)
        difference = np.abs(hi - fft)
        maximum = int(np.argmax(delta))
        result['rows'].append({'aperture': fn, 'height': height,
                               'max_pupil128_to_256_change': float(delta.max()),
                               'max_huygens256_minus_fft512_difference': float(difference.max()),
                               'worst_sampling_change_frequency_lp_mm': [5, 10, 20][maximum // 2],
                               'worst_sampling_change_direction': ['T', 'S'][maximum % 2],
                               'FFT512_values': fft.tolist(), 'Huygens128_values': lo.tolist(),
                               'Huygens256_values': hi.tolist()})
    if result['reasons']:
        result['status'] = 'not_ready'
        return result
    result['max_pupil_sampling_change'] = max(row['max_pupil128_to_256_change'] for row in result['rows'])
    result['max_huygens256_fft512_difference'] = max(row['max_huygens256_minus_fft512_difference'] for row in result['rows'])
    result['status'] = 'unconverged_spot_sampling' if result['max_pupil_sampling_change'] > threshold else 'two_level_spot_difference_within_screening_threshold'
    return result


def main():
    v = read(R / 'validated.json')
    target = read(R / v.get('target_file', 'target_optimization.json'))
    curves = read(R / 'field_curves.json')
    final_hash = source_hash(v)
    if final_hash is None:
        raise ValueError('validated.json requires a valid frozen-source source_sha256.')
    if source_hash(curves) != final_hash:
        raise ValueError('Mandatory field_curves.json source_sha256 is missing or differs from validated.json.')
    if curves.get('sampling') != 512:
        raise ValueError('GENERAL report plots require native FFT512 field_curves.json.')
    if v.get('sampling') != {'5.6': 1024, '8': 512, '22': 512}:
        raise ValueError('GENERAL report quantitative audit requires FFT1024 at f/5.6 and FFT512 at f/8 and f/22.')
    dc = read(P / 'revision2' / 'drawing_constraints.json')
    old = read(P / 'revision2' / 'validated.json')
    sur = v['surfaces']
    if len(sur) != 12 or any('conic' not in s or float(s['conic']) != 0 for s in sur):
        raise ValueError('GENERAL requires explicit zero conic on all twelve surfaces.')
    if float(v.get('asphere_conic', 0)) != 0:
        raise ValueError('GENERAL top-level asphere_conic must also be zero.')
    signature = surface_signature(sur)
    if [s['surface'] for s in signature] != list(range(1, 13)):
        raise ValueError('GENERAL surface signature must contain each surface 1 through 12 exactly once.')
    signature_sha256 = hashlib.sha256(json.dumps(signature, sort_keys=True, separators=(',', ':'), allow_nan=True).encode('utf-8')).hexdigest()
    coef = np.asarray(v.get('asphere_A4_to_A6', []), dtype=float)
    if len(sur) != 12 or coef.shape != (2,):
        raise ValueError('GENERAL requires 12 surfaces and exactly two coefficients: A4, A6.')
    for key in ['asphere_A4_to_A12', 'asphere_A4_to_A16']:
        if key in v and np.any(np.asarray(v[key], dtype=float)[2:] != 0):
            raise ValueError(f'GENERAL forbids nonzero A8 and higher: {key}')
    if 'asphere_powers' in v and list(v['asphere_powers']) != [4, 6]:
        raise ValueError('GENERAL asphere_powers must be [4, 6].')
    powers = np.asarray([4, 6])
    old_coef = np.asarray(old.get('asphere_A4_to_A16', old['asphere_A4_to_A12']), dtype=float)
    old_coef = np.pad(old_coef, (0, max(0, len(coef) - len(old_coef))))[:len(coef)]
    audit_path = R / 'mapping_pupil_focus_audit.json'
    audit, audit_unverified_reason = optional_current(audit_path, final_hash)
    if audit is not None and ('official_image_distance_mm' not in audit or abs(float(audit['official_image_distance_mm']) - sur[-1]['thickness_mm']) > 1e-7):
        audit = None
        audit_unverified_reason = '审核像距缺失或与最终共同像面不一致；不引用该文件任何数值。'
    manufacturing_path = R / 'manufacturing_geometry_metrics.json'
    manufacturing, manufacturing_unverified_reason = optional_current(manufacturing_path, final_hash)
    if manufacturing is not None and (manufacturing.get('surface_signature') != signature or manufacturing.get('surface_signature_sha256') != signature_sha256):
        manufacturing = None
        manufacturing_unverified_reason = '十二面 surface_signature 缺失或与最终处方不一致；不引用该文件任何数值。'
    diffraction_path = R / 'diffraction_reference.json'
    diffraction = read(diffraction_path) if diffraction_path.exists() else None
    hspot = huygens_spot_summary(v, curves)
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
                       'source_sha256': final_hash, 'surface_signature': signature,
                       'surface_signature_sha256': signature_sha256,
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
    axs[0].set(xlim=(-4, max(82, z[-1] + 4)), ylim=(-44, 44), title='GENERAL optical section: full 105-degree field')
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
            if col == 0:
                ax.set_ylabel('MTF', fontsize=13)
            if row == 2:
                ax.set_xlabel('Reference image height / 193 mm (%)', fontsize=13)
    fig.suptitle('GENERAL FFT512 curves: blue/green = model; orange/red/purple = manual\nQuantitative audit: f/5.6 FFT1024; f/8 and f/22 FFT512. No point markers.', fontsize=14)
    handles, labels = axs[0, 0].get_legend_handles_labels()
    order = [0, 1, 2, 3, 4, 5]
    fig.legend([handles[k] for k in order], [labels[k] for k in order], ncol=3,
               fontsize=12, loc='lower center', bbox_to_anchor=(.5, .005), frameon=False)
    fig.tight_layout(rect=(0, .10, 1, .94))
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
    summary = {'source_sha256': final_hash, 'surface_signature_sha256': signature_sha256,
               'per_aperture': metrics, 'full_field_deg': v['full_field_deg'], 'min_air_gap_mm': min_gap,
               'all_points_at_or_above_reference': bool(np.all(np.asarray(all_delta) >= 0)),
               'all_points_within_2pp_readout_band': bool(np.all(np.asarray(all_delta) >= -.02)),
               'all_points_within_4pp_readout_band': bool(np.all(np.asarray(all_delta) >= -.04)),
               'all_comparisons_directly_validated': all(m['interpolated_reference_points'] == 0 for m in metrics.values()),
               'same_image_plane_verified': same_image, 'image_distances_mm': image_values,
               'manufacturer_readout_uncertainty_mtf': [.02, .04], 'geometry': geometry_output,
               'comparison': comparison, 'audit_file_available': audit is not None,
               'manufacturing_metrics_available': manufacturing is not None,
               'audit_unverified_reason': audit_unverified_reason,
               'manufacturing_unverified_reason': manufacturing_unverified_reason,
               'diffraction_reference_available': diffraction is not None,
               'huygens_spot_check': hspot,
               'scope': 'Discrete audited reference points, not proof over all continuous field positions.'}
    (R / 'acceptance.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')

    pdfmetrics.registerFont(TTFont('SXL', r'C:\Windows\Fonts\simhei.ttf'))
    styles = {
        'title': ParagraphStyle('title', fontName='SXL', fontSize=20, leading=28, spaceAfter=15, textColor=colors.HexColor('#17384b')),
        'h': ParagraphStyle('h', fontName='SXL', fontSize=13, leading=19, spaceBefore=10, spaceAfter=6, keepWithNext=True, textColor=colors.HexColor('#17384b')),
        'body': ParagraphStyle('body', fontName='SXL', fontSize=9.6, leading=15, spaceAfter=7, wordWrap='CJK'),
        'small': ParagraphStyle('small', fontName='SXL', fontSize=8, leading=12, spaceAfter=4, wordWrap='CJK')}
    md = ['# Super-Symmar XL 150 mm f/5.6 光学性能与制造可能性报告 - GENERAL\n']
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
        c.setSubject('GENERAL source SHA256: ' + final_hash)
        c.setFont('SXL', 8)
        c.setFillColor(colors.HexColor('#77838c'))
        c.drawString(40, 26, 'Super-Symmar XL 150 mm | GENERAL reverse candidate')
        c.drawRightString(555, 26, str(d.page))

    strict = summary['all_points_at_or_above_reference']
    direct = summary['all_comparisons_directly_validated']
    outcome = ('本次审核的离散对照点均达到或超过重新量读的原厂 MTF。' if strict else '本次审核仍有离散对照点低于重新量读的原厂 MTF，尚未满足全点达到或超过的目标。')
    if not direct:
        outcome += ' 部分对照值由高采样结果沿视场插值，不能表述为全部对照点均经直接复算。'
    outcome += (' 受检光学表面区域未发现交叠。' if no_overlap else ' 几何检查发现非正间隙或厚度，不能进行制造放行。')
    story.append(Paragraph('光学性能与制造可能性报告<br/>Super-Symmar XL 150 mm f/5.6 - GENERAL', styles['title']))
    section('方案与材料身份', '面型与材料通用优化方案' + '。本报告仅引用本方案冻结 best 的原生复算，不将其等同于旧 R4 材料或处方。材料替换并不自动带来性能提高或实测降本。')
    material_path = R / 'material_catalog_audit.json'
    material_data = read(material_path) if material_path.exists() else None
    if material_data and material_data.get('source_sha256') == v['source_sha256']:
        tab([['片 / 前面', '历史参考玻璃', '本方案原生材料', '原生目录候选'], *[[f"L{row['element']} / S{row['surface']}", row['historical_reference_glass'], row['native_material'], ', '.join(row['catalogs_in_use_containing_material']) or '未解析'] for row in material_data['elements']]], [75, 135, 140, 165])
        section('材料供应与报价边界', '此表只核验 native 名称、目录归属及历史材料替换关系。目录存在不代表毛坯可买；没有供应商正式报价、相同批量规格、熔次与工艺询价，不报告确定的价格节省比例、成本或交期。全 CDGM 仅表示处方材料来源约束，不证明配方等同原厂。')
    else:
        section('材料目录身份未核验', '材料审核缺失或冻结 hash 不一致，不引用旧材料表及任何报价推断。')

    hspot_scope = ('本轮 A6 Huygens 两级瞳采样抽查已记录，但未构成完整收敛验证。' if hspot['status'] not in ['not_present', 'not_ready'] else '本轮 A6 Huygens 独立抽查未完成或记录尚不满足同模型同设置要求。')
    section('结论与判定边界', outcome + ' 本轮将非球面最高阶限制为 A6，只含 A4、A6，不允许 A8 及更高项。下表为本轮原生 FFT 结果；' + hspot_scope + ' 不使用 R3 高阶候选的 Huygens 结果代替。原厂扫描图人工读数的不确定度约为 2-4 个百分点；严格达到读数、在读图误差带内相容，以及连续全视场都优于原厂，是不同的判断。本报告不将后两者替代严格离散点判定，也不承诺量产性能。')
    tab([['光圈', '最大低于原厂\n百分点', '严格达到下限\n样点数', '不足不超过 4 点\n样点数'], *[[f'f/{fn}', f"{100*m['max_shortfall']:.2f}", f"{m['points_at_or_above_reference']} / {m['points']}", f"{m['within_4_percentage_point_lower_bound']} / {m['points']}"] for fn, m in metrics.items()]], [65, 140, 145, 165])
    section('手册数据来源', '本轮采用 target_optimization.json 中的手册目标，来源为 R3 已独立审核的密集人工数字化读数，不能当作原厂原始数值表。橙、红、紫色线为手册读数折线，蓝、青、绿色线为本轮 A6 模拟结果。未公开参考线的视场不推定原厂 MTF 为零，旧目标不同条件下的结果不直接用于本轮优劣判定。')
    if endpoint_notes:
        section('公开曲线终点', ' '.join(endpoint_notes) + ' 若该点没有最终直接复算记录，验收统计使用完整视场高采样曲线插值并明确披露，不因初期优化目标文件遗漏而排除。')
    section('审核数据说明', '手册数据对应用户提供的 PDF 第 2 页无限远物距一行，保留原始扫描图和旧读数用于追溯。f/8 的 78% 终点应包含在本轮验收中；实际是否直接复算由 acceptance.json 的直接/插值点数量判定。')
    section('模型与共同模拟条件', f"无限远物距、平面像面；全部光圈均保留 {v['full_field_deg']:.1f}° 全视场，最大半视场 {max(v['field_angles_deg']):.4f}°。采用原厂 546、644、588、480、436、405 nm，权重 24.6、18.6、22.1、12.4、15.2、7.1%。MTF 比较采用 5、10、20 lp/mm；列次序为 T、S，S 实线、T 虚线。光阑半口径解算：{v.get('stop_solve', '未记录')}。")
    plane = ('三文件同像面已由验证数据明确记录。' if same_image else '验证数据尚未明确记录三文件同像面重读证明。' if same_image is None else '三档光圈像面不一致，比较条件不合格。')
    section('统一像面', f"本报告不为不同光圈分别移动像面。末面到像面名义距离为 {sur[-1]['thickness_mm']:.8f} mm。{plane} 三档记录：" + '；'.join(f'f/{fn}: {dist:.8f} mm' for fn, dist in image_values.items()) + '。原厂聚焦程序的完全等效性仍须由实际验证流程确认，不能仅凭焦距与像距接近推断。')

    section('采样收敛与误差', '图中完整视场曲线均采用原生 FFT512；定量验收 f/5.6 为 FFT1024，f/8 与 f/22 为 FFT512。收敛表比较同一处方、同一聚焦条件下的最终高采样与 256 采样。该差异检查数值稳定性，不代表制造公差、原厂读图精度或实物 MTF。完整曲线必须与 validated.json 的冻结 source_sha256 一致，附加审核文件身份缺失或不一致时不引用其数值。')
    story.extend([PageBreak(), par('FFT 模拟 MTF 与手册 MTF 对比', 'h'), Image(str(R / 'MTF_full_field.png'), width=515, height=515)])
    md.append('## 模拟 MTF 与手册 MTF 对比\n\n![MTF](MTF_full_field.png)\n')
    section('图线与视场说明', '每行分别为 f/5.6、f/8、f/22，每列分别为 S、T 方向。共享图例放在六个绘图区外的下方，列出模拟与手册的三种频率，全部曲线不使用点标记。横坐标以手册最大像高 193 mm 归一化，灰色区仅表示没有公开参考曲线，不改变模型最大视场。折线之间的细节不能视为原厂公开的连续数值。')
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
    section('S10 最高 A6 偶次非球面', 'z(r)=c*r^2/[1+sqrt(1-(1+k)*c^2*r^2)]+A4*r^4+A6*r^6，其中 c=1/R。本轮仅有 A4、A6，A8 及更高项必须为零。脚本发现非零高阶项会停止生成报告。系数采用 mm 单位，必须与曲率半径共同使用，不能解释为面形误差公差。光阑行是 f/5.6 时的自动半口径，其它光圈由原生模型自动解算。')
    tab([['参数', 'GENERAL 最终数值', '单位'], ['圆锥常数 k', str(sur[9].get('conic', v.get('asphere_conic', 0))), '无量纲'], *[[f'A{power}', f'{a:.12e}', f'mm^({1-power})'] for a, power in zip(coef, powers)]], [80, 290, 145])

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
    section('结构变化按最终数据统计', '以下变化由最终 GENERAL 与 R2 的 validated.json 逐面比较得出，不假设本轮实际使用了哪组优化变量或限制。未列出的对应数值在 1e-8 mm 比较阈值内一致。S12 间隔变化表示共同像面的变化，不是镜片中心厚度。')
    tab([['面号', 'GENERAL - R2'], *(changed or [['全部面', '处方表中的曲率、间隔、口径与玻璃未检出变化']])], [70, 445])
    section('非球面与一阶参数变化', 'A4、A6 系数相对 R2 对应项的差值依次为：' + '；'.join(f'{a-b:+.6e}' for a, b in zip(coef, old_coef)) + '。R2/R3 的非零高阶项属于历史候选，本轮没有沿用它们。本轮有效焦距为 ' + f"{v['first_order']['EFFL']:.6f} mm，入瞳位置为 {v['first_order']['ENPP']:.6f} mm，首面到末面的轴向长度为 {z[-1]:.6f} mm。原厂公开对应值约为 148.1、36.6、77.4 mm；参数接近不代表完整处方已被唯一恢复。")
    section('材料采购与加工', '处方中玻璃是完整色散目录候选，其名称和在 Zemax 中存在不等于已确认现货或毛坯可用。应取得供应商实际熔次色散、均匀性、退火、尺寸和环境稳定性数据；更换玻璃需在全波段重新优化。胶合组外非球面需要加工、定心与独立面形检测方案，明确有效口径、基准球、边缘余厚、胶层及倒角后才可询价。')
    story.extend([PageBreak(), par('年代加工技术与制造证据', 'h')])
    section('年代工艺背景与 A6 限制', '本轮按原镜头年代的制造约束审视非球面，减少高阶自由度至 A4、A6。但多项式阶数低不自动证明当年或今天可制造：同样的 A6 曲面仍可能有较大的设计离开量、斜率变化或边缘加工负担。是否适合相应年代的工艺，需要有效口径、PV、最大斜率、检测基准、材料毛坯、胶合与定心方案，以及制造商或实物证据共同判断。此处不凭系数阶数推定历史工艺、加工精度或良率。')
    historical_path = R / 'historical_manufacturing_audit.md'
    if historical_path.exists():
        section('厂家主源与证据边界', '施耐德 Aspheric technology 技术文献明确列出 XL ASPHERIC 150/5.6，并说明小区域数控成形/抛光、CGH 辅助干涉检测和反馈修正抛光路线。此证据强于按年代猜测设备能力。但公开 PDF 未标日期，不能据此断言 1996 年某批实物使用同一设备和规范。文献中的约 1.5 mm 离开量、全局小于 1 μm 等说明值未明确对应本镜头，不作为当前处方公差、能力上限或生产保证。')
        section('专利、低阶限制与制造预审', 'US5870234A 的德国优先权为 1996-09-06，公开日为 1999-02-09；它没有公开原厂非球面系数或多项式阶数，附图为示意。A4/A6 限制来自本轮用户要求，不是专利恢复出的事实。年代预审将数控非球面加工与干涉检测反馈列为候选工艺路线，仍需核实当时小口径玻璃加工、CGH 和设备可达精度；不据此断定当年实物使用同一方案。当前候选的精度、成本及良率需工艺、公差和样机验证。k 的贡献必须与 A4/A6 一并记录。')
        story.append(Paragraph('制造主源：<link href="https://schneiderkreuznach.com/application/files/3515/0781/8891/aspheric-technology.pdf" color="#24628a">施耐德 Aspheric technology</link>；<link href="https://patents.google.com/patent/US5870234A/en" color="#24628a">US5870234A 专利</link>。详细主源范围见 historical_manufacturing_audit.md。', styles['small']))
        md.append('制造主源：[施耐德 Aspheric technology](https://schneiderkreuznach.com/application/files/3515/0781/8891/aspheric-technology.pdf)，[US5870234A](https://patents.google.com/patent/US5870234A/en)。\n')
    else:
        section('年代制造主源未核验', '没有 historical_manufacturing_audit.md，未完成本轮年代制造主源审核；低阶曲面本身不能证明原厂工艺或相应年代制造能力。')
    section('制造可能性的当前结论', outcome + ' 即使理想 MTF 达到原厂，也只是名义设计结果。本轮没有曲率、厚度、间距、偏心、倾斜、非球面误差、胶层、装配补偿和温度的完整公差分析，没有 Monte Carlo 良率或样机实测。因此可以继续设计评估，不能据此声明直接量产、生产良率、成本或交期。')

    story.extend([PageBreak(), par('非球面加工描述与镜片厚度检查', 'h')])
    if manufacturing is None:
        section('制造几何描述未核验', (manufacturing_unverified_reason or '无有效制造记录。') + ' 尚未核验最终处方的非球面离开量、表面斜率及镜片边缘厚度，不引用该文件任何数值或轮廓图。前文由最终处方独立重算的间隙不能替代这些指标。')
    else:
        a = manufacturing['asphere']
        stored = np.asarray(a['coefficients'], dtype=float)
        coefficients_match = len(stored) == len(coef) and np.allclose(stored, coef, rtol=1e-8, atol=0)
        radius_match = abs(a['prescribed_vertex_radius_mm'] - sur[9]['radius_mm']) < 1e-7
        if not coefficients_match or not radius_match:
            section('制造指标与最终输入不一致', '现有 manufacturing_geometry_metrics.json 的系数或顶点曲率与本次 validated.json 不一致，不能作为本次最终处方的制造几何证明。必须重新运行 finalize_overnight.py --phase general --prepare-only；本报告不引用其旧非球面数值。')
        else:
            section('非球面离开量与斜率', f"S10 有效半径 {a['clear_radius_mm']:.3f} mm；参考为处方指定顶点半径球面，不是拟合最佳球面。设计离开量范围 {a['departure_min_um']:.3f} 至 {a['departure_max_um']:.3f} μm，PV {a['departure_pv_um']:.3f} μm；最大绝对表面斜率 {a['maximum_absolute_surface_slope_mm_per_mm']['value']:.6f} mm/mm，最大绝对斜率离开量 {a['maximum_absolute_slope_departure_mm_per_mm']['value']:.6f} mm/mm；最大绝对表面倾角 {a['maximum_absolute_surface_angle_deg']['value']:.4f}°。这些是设计面形及斜率，不能称为要求工厂达到的误差公差。")
            profile = R / 'asphere_profile.png'
            if profile.exists() and manufacturing.get('asphere_profile_sha256') == hashlib.sha256(profile.read_bytes()).hexdigest():
                story.append(Image(str(profile), width=515, height=328))
                md.append('![非球面设计轮廓](asphere_profile.png)\n')
            else:
                section('轮廓图未核验', 'asphere_profile.png 缺失或其 SHA256 与本次制造指标记录不一致，不引用该图；以上仅引用已验证身份的制造几何数值。')
            tab([['镜片 / 玻璃', '中心厚度 mm', '共同口径边缘厚度 mm', '受检最薄处 mm'], *[[f"L{e['element']} / {e['glass']}", f"{e['center_thickness_mm']:.5f}", f"{e['edge_thickness_mm']:.5f}", f"{e['minimum_thickness_mm']:.5f}"] for e in manufacturing['glass_elements']]], [145, 110, 145, 115])
            section('厚度检查范围', f"采用 {manufacturing['radial_sample_count']} 个均匀径向样点，曲面导数按储存的圆锥加偶次多项式解析计算。镜片厚度只覆盖前后光学面的共同有效口径，未定义的倒角和机械外缘不在检查域内。制造指标中的保守后组间隙为 {manufacturing['rear_gap_conservative_extension']['minimum_gap_mm']:.5f} mm；这也不是带公差的装配最小间隙。")

    story.extend([PageBreak(), par('实际像高、瞳面与原厂聚焦审核', 'h')])
    if audit is None:
        section('原生光线与聚焦审核未核验', (audit_unverified_reason or '无有效审核记录。') + ' 不能确认最终处方的实际主光线像高、入瞳遮挡、原生照度或 f/5.6 轴上20 lp/mm聚焦条件，不引用该文件任何数值。前文离散 MTF 统计不构成这些条件已核验的证明。')
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
    if hspot['status'] in ['not_present', 'not_ready']:
        section('A6 候选独立抽查未完成', '；'.join(hspot['reasons']) + ' 本报告不沿用 R3 Huygens 曲线或数值作为 A6 证明。FFT 高采样收敛也不能自动证明宽角度出瞳假设完全成立。')
    else:
        section('本轮 A6 Huygens 两级瞳面抽查', '两份记录均已完成且无失败，模型与最终 source_candidate 一致，五个场点均为零像距偏移。固定像面 512 × 512、间距 1 μm，分别采用瞳面 128 和 256；下表每项取 5、10、20 lp/mm 的 T/S 六个值的最大绝对差。FFT 对照来自本轮完整视场 512 采样曲线在相同参考场点的插值，不引用 R3 数据。')
        tab([['光圈 / h', '128-256最大变化\n百分点', '256与FFT512最大差\n百分点', '最大变化频率 / 方向'],
             *[[f"f/{row['aperture']} / {row['height']:.2f}", f"{100*row['max_pupil128_to_256_change']:.4f}", f"{100*row['max_huygens256_minus_fft512_difference']:.4f}", f"{row['worst_sampling_change_frequency_lp_mm']} lp/mm {row['worst_sampling_change_direction']}"] for row in hspot['rows']]], [80, 135, 155, 145])
        screen = 100 * hspot['screening_threshold_mtf']
        if hspot['status'] == 'unconverged_spot_sampling':
            section('瞳面采样尚未收敛', f"本次两级瞳采样最大变化 {100*hspot['max_pupil_sampling_change']:.4f} 个百分点，超过抽查筛选阈值 {screen:.2f} 个百分点。不得称为计算通过或以偏高 Huygens 数值声明优于原厂，需增加瞳面采样并检查像面间距与窗口。")
        else:
            section('两级抽查的有限结论', f"五场点两级瞳采样变化未超过 {screen:.2f} 个百分点的抽查阈值，只表明这些点的两个采样级别相容；两级样本不能证明瞳面积分充分收敛，更不证明固定像面间距和计算窗口已收敛。不得称为完整独立复核通过。")
        section('交叉差异与验收边界', 'Huygens 与 FFT 差异说明当前计算方法的一致性仍需调查；筛选阈值不是光学设计公差、厂家读图精度或制造误差预算。该五场点抽查不替代完整视场 MTF 验收，本报告仅将其作为本轮 A6 的独立方法检查记录。')
    story.append(Paragraph('方向定义来源：<link href="https://schneiderkreuznach.com/en/industrial-optics/knowledge-hub/modulation-transfer-function" color="#24628a">施耐德 MTF 说明</link>（T 虚线、S 实线）。计算假设来源：<link href="https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v252/en/OpticStudio_User_Guide/OpticStudio_Help/topics/FFT_MTF.html" color="#24628a">Ansys FFT MTF 文档</link>（2025 R2 文档；本机计算版本为 2023 R1）。', styles['small']))
    md.append('方向定义：[施耐德 MTF 说明](https://schneiderkreuznach.com/en/industrial-optics/knowledge-hub/modulation-transfer-function)。计算假设：[Ansys FFT MTF 文档](https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v252/en/OpticStudio_User_Guide/OpticStudio_Help/topics/FFT_MTF.html)。\n')
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
    section('复算数据与文件', 'overnight_20260915/general/validated.json：本轮最高 A6 候选的最终高采样离散 MTF、处方与一阶数据。overnight_20260915/general/field_curves.json：本轮完整视场模拟曲线。overnight_20260915/general/target_optimization.json：本轮正式手册目标。revision2/validated.json：历史处方结构对照；revision2/drawing_constraints.json：结构图定标记录。revision3 中的高阶候选与 Huygens 初审仅属于历史资料，不代表本轮 A6 处方已复核。全部产出保存在 SuperSymmarXL 文件夹中。')
    section('原始资料', '用户提供的 super-symmar_xl_56_150.pdf：公开性能、光谱权重、视场及结构示意。用户提供的 US5870234 Super Symmar XL patent.pdf：结构与专利实施例参考。公开数据不足以唯一恢复原厂实际处方、非球面、制造尺寸及公差；本报告的 ZMX 是可复算的逆向候选，不是经过原厂认证的生产处方。')
    name = '光学性能与制造可能性报告_GENERAL'
    SimpleDocTemplate(str(R / (name + '.pdf')), pagesize=(595, 842), leftMargin=40, rightMargin=40,
                      topMargin=38, bottomMargin=42).build(story, onFirstPage=footer, onLaterPages=footer)
    (R / (name + '.md')).write_text('\n'.join(md), encoding='utf-8')
    print(json.dumps({k: x for k, x in summary.items() if k not in ['comparison', 'geometry']}, indent=2))


if __name__ == '__main__':
    main()


