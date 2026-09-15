"""Freeze and validate one isolated overnight scheme, then optionally author PDF.

No native instances are opened by importing or --stage-scripts-only. --prepare-only
runs native validation without PDF. --author-only explicitly requests PDF; the caller runs the PDF skill marker
explicitly once for its intended report count before the first authoring command.
Each native subprocess uses one standalone app; --workers is a concurrency budget,
not a request to open redundant apps. General refuses a budget above two apps.
"""
from pathlib import Path
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import math
import shutil
import subprocess
import sys

P = Path(__file__).resolve().parents[1]
BASE = P / 'overnight_20260915'
PHASES = {'general': ('GENERAL', '面型与材料通用优化方案'), 'cdgm': ('CDGM', '全 CDGM 材料优化方案')}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def atomic_state(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    write(temporary, value)
    temporary.replace(path)


def prepare(phase, folder):
    """Copy reviewed R4 logic, replacing only paths and scheme identifiers."""
    code, label = PHASES[phase]
    pipeline = folder / '_pipeline'
    pipeline.mkdir(parents=True, exist_ok=True)
    templates = {'probe_zos.py': 'probe_zos.py', 'validate.py': 'validate_revision4.py',
                 'curve.py': 'curve_revision4.py', 'mapping.py': 'audit_revision4_mapping.py',
                 'integrity.py': 'final_integrity_revision4.py',
                 'manufacturing.py': 'manufacturing_metrics_revision4.py', 'report.py': 'report_revision4.py'}
    for destination, source in templates.items():
        text = (P / 'scripts' / source).read_text(encoding='utf-8-sig')
        text = text.replace('ROOT=Path(__file__).resolve().parents[1]', f'ROOT=Path({str(P)!r})')
        text = text.replace('P = Path(__file__).resolve().parents[1]', f'P = Path({str(P)!r})')
        text = text.replace('P=Path(__file__).resolve().parents[1]', f'P=Path({str(P)!r})')
        for anchor in ["R=ROOT/'revision4'", "R = P / 'revision4'", "R = P/'revision4'"]:
            text = text.replace(anchor, f'R = Path({str(folder)!r})')
        text = text.replace("default=P/'revision4/validated.json'", f"default=Path({str(folder / 'validated.json')!r})")
        text = text.replace("default=P/'revision4/SuperSymmarXL_150_R4_f5p6.zmx'", f"default=Path({str(folder / ('SuperSymmarXL_150_' + code + '_f5p6.zmx'))!r})")
        text = text.replace('R4', code)
        if destination == 'report.py':
            # Keep legacy-directory references historical; never borrow its curves.
            text = text.replace('revision4/', f'overnight_20260915/{phase}/')
            text = text.replace('manufacturing_metrics_revision4.py', f'finalize_overnight.py --phase {phase} --prepare-only')
            anchor = f"    story.append(Paragraph('光学性能与制造可能性报告<br/>Super-Symmar XL 150 mm f/5.6 - {code}', styles['title']))"
            insertion = (
                f"    section('方案与材料身份', {label!r} + '。本报告仅引用本方案冻结 best 的原生复算，不将其等同于旧 R4 材料或处方。材料替换并不自动带来性能提高或实测降本。')\n"
                "    material_path = R / 'material_catalog_audit.json'\n"
                "    material_data = read(material_path) if material_path.exists() else None\n"
                "    if material_data and material_data.get('source_sha256') == v['source_sha256']:\n"
                "        tab([['片 / 前面', '历史参考玻璃', '本方案原生材料', '原生目录候选'], *[[f\"L{row['element']} / S{row['surface']}\", row['historical_reference_glass'], row['native_material'], ', '.join(row['catalogs_in_use_containing_material']) or '未解析'] for row in material_data['elements']]], [75, 135, 140, 165])\n"
                "        section('材料供应与报价边界', '此表只核验 native 名称、目录归属及历史材料替换关系。目录存在不代表毛坯可买；没有供应商正式报价、相同批量规格、熔次与工艺询价，不报告确定的价格节省比例、成本或交期。全 CDGM 仅表示处方材料来源约束，不证明配方等同原厂。')\n"
                "    else:\n"
                "        section('材料目录身份未核验', '材料审核缺失或冻结 hash 不一致，不引用旧材料表及任何报价推断。')\n"
            )
            if anchor not in text:
                raise RuntimeError('Report template changed: cannot insert scheme/material section safely.')
            text = text.replace(anchor, anchor + '\n' + insertion, 1)
            if phase == 'cdgm':
                cost_anchor = "    story.extend([PageBreak(), par('衍射参考与验证边界', 'h')])"
                cost_section = (
                    "    story.extend([PageBreak(), par('全 CDGM 材料与目录成本取舍', 'h')])\n"
                    "    cost_path = R / 'catalog_tradeoff_audit.json'\n"
                    "    cost = read(cost_path) if cost_path.exists() else None\n"
                    "    if not cost or cost.get('source_sha256') != v['source_sha256'] or not cost.get('selected_cost_proxy_verified'):\n"
                    "        section('目录成本代理未核验', '目录、manifest、材料身份或冻结候选链未完整核对，不引用不明来源 OD 或价格。' + ('；'.join(cost.get('reasons', [])) if cost else ''))\n"
                    "    else:\n"
                    "        section('选定六片的同目录 OD', '以下 OD 第一项取自冻结 CDGM AGF 的同目录相对成本，六片未加权求和只用于该目录内部筛选，不是毛坯或成镜价格。历史混合材料只列对应关系，不以其 SCHOTT OD 比较节省比例。')\n"
                    "        tab([['片 / 前面', '历史混合材料', '选定 CDGM', 'OD 相对成本'], *[[f\"L{row['element']} / S{row['surface']}\", row['historical_reference_glass'], row['native_material'], f\"{row['catalog_relative_cost']:.4f}\"] for row in cost['selected_elements']]], [80, 145, 165, 125])\n"
                    "        section('所选目录代理', f\"六片 OD 未加权合计 {cost['selected_sum_six_element_relative_cost']:.4f}；目录标题 {cost['CDGM_catalog_header']}。原始 OD 行、manifest/目录 snapshot hash 和 catalog_plan hash 保存在 catalog_tradeoff_audit.json。无供应商正式人民币报价、尺寸/熔次/数量/工艺询价，不报告实测降本或跨目录节省百分比。\")\n"
                    "        if cost.get('display_candidates'):\n"
                    "            tab([['候选与六片组合', 'CDGM OD 和', '筛选最大不足 / 点', '筛选采样', '最终高采样复核'], *[[row['label'] + '\\n' + ' / '.join(row['materials']), f\"{row['sum_six_element_relative_cost']:.4f}\", f\"{100*row['screening_max_shortfall']:.3f}\", str(row.get('screening_sampling', '未记录')), '已完成：本方案' if row['is_selected_source'] else '未独立复核'] for row in cost['display_candidates']]], [205, 70, 95, 55, 90])\n"
                    "        section('性能与成本候选边界', cost['tradeoff_interpretation'])\n"
                    "        section('筛选可行不等于生产可行', '表中未独立复核的组合仅为优化筛选值，其“可行”指当时几何与一阶参数门槛。它不表示高采样已验证、MTF 全面达到手册、供应可买或制造放行。全球筛选分数最佳可能不是 OD 最低；选择目录代理较低的组合前必须冻结该候选并重新完成同条件高采样、像高/聚焦、几何、公差与样机验证。')\n"
                    "        for reason in cost.get('reasons', []):\n"
                    "            story.append(par('成本审核边界：' + reason, 'small'))\n"
                )
                if cost_anchor not in text:
                    raise RuntimeError('Report template changed: cannot insert CDGM tradeoff section safely.')
                text = text.replace(cost_anchor, cost_section + cost_anchor, 1)
        if destination == 'mapping.py':
            text = text.replace('Run only after optimization instances exit.', 'Independent standalone app within the supervisor concurrency budget.')
        compile(text, str(pipeline / destination), 'exec')
        (pipeline / destination).write_text(text, encoding='utf-8')
    material_text = material_audit_script(folder, code, phase)
    compile(material_text, str(pipeline / 'materials.py'), 'exec')
    (pipeline / 'materials.py').write_text(material_text, encoding='utf-8')
    # These are historical evidence, not borrowed current optical results.
    for reference in ['historical_manufacturing_audit.md', 'diffraction_reference.json', 'R2_same_condition_baseline.json']:
        source = P / 'revision4' / reference
        destination = folder / reference
        if source.exists() and not destination.exists():
            shutil.copy2(source, destination)
    target = folder / 'target_optimization.json'
    if not target.exists():
        shutil.copy2(P / 'revision4' / 'target_optimization.json', target)
    return pipeline


def material_audit_script(folder, code, phase):
    # API methods were verified by reflecting installed ZOSAPI_Interfaces:
    # ISystemData.MaterialCatalogs -> GetAvailableCatalogs, GetCatalogsInUse,
    # GetMaterialsInCatalog. No speculative catalog API names are used.
    return f'''from pathlib import Path
import json,csv,hashlib
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
R=Path({str(folder)!r})
v=json.loads((R/'validated.json').read_text(encoding='utf-8'))
try:
 model=R/v['files'][0]
 assert hashlib.sha256(model.read_bytes()).hexdigest()==v['official_file_sha256'][model.name]
 sys.LoadFile(str(model),False)
 catalogs=sys.SystemData.MaterialCatalogs
 available=list(map(str,catalogs.GetAvailableCatalogs()))
 in_use=list(map(str,catalogs.GetCatalogsInUse()))
 def catalog_materials(catalog):
  # ZOS-API can return null for a catalog token that is present in the
  # in-use list but has no enumerable glass rows.  Treat that token as an
  # empty set; actual glass surfaces still have to resolve in a real catalog.
  values=catalogs.GetMaterialsInCatalog(catalog)
  return set(map(str,values)) if values is not None else set()
 # User catalogs in the loaded file can be absent from GetAvailableCatalogs;
 # GetCatalogsInUse is authoritative for those resolved surface materials.
 catalog_ids=list(dict.fromkeys([c for c in available+in_use if c]))
 names={{catalog:catalog_materials(catalog) for catalog in catalog_ids}}
 cdgm_catalogs=[catalog for catalog in catalog_ids if catalog.upper()=='CDGM']
 cdgm_names=set()
 for catalog in cdgm_catalogs:cdgm_names.update(catalog_materials(catalog))
 historical=json.loads((ROOT/'revision2'/'validated.json').read_text(encoding='utf-8'))
 previous={{int(s['surface']):s['glass'] for s in historical['surfaces']}}
 elements=[]
 for element,i in enumerate([1,3,5,8,9,11],1):
  material=str(sys.LDE.GetSurfaceAt(i).Material)
  solve=str(sys.LDE.GetSurfaceAt(i).MaterialCell.GetSolveData().Type)
  assert solve in ['Fixed','None'],'Material must resolve through a fixed catalog, not a model/offset/substitution solve'
  # A glass name can also exist in unrelated installed catalogs.  Resolution
  # ambiguity is determined only among catalogs actually loaded by this file.
  containing=[catalog for catalog in in_use if catalog and material in names[catalog]]
  elements.append({{'element':element,'surface':i,'historical_reference_glass':previous[i],
   'native_material':material,'native_material_solve':solve,'catalogs_in_use_containing_material':containing,
   'member_of_available_CDGM_catalog':material in cdgm_names,
   'unambiguous_CDGM_resolution':bool(containing) and all(c.upper()=='CDGM' for c in containing)}})
 print('CATALOG_DIAGNOSTIC',json.dumps({{'available':available,'in_use':in_use,'cdgm_catalogs':cdgm_catalogs,
  'cdgm_material_count':len(cdgm_names),'elements':elements}},ensure_ascii=True),flush=True)
 assert all(row['native_material'] and row['catalogs_in_use_containing_material'] for row in elements),'Unresolved or modeled material cannot certify catalog identity'
 all_cdgm=bool(cdgm_catalogs) and all(row['member_of_available_CDGM_catalog'] and row['unambiguous_CDGM_resolution'] for row in elements)
 if {phase!r}=='cdgm':assert all_cdgm,'CDGM phase requires all six native materials to resolve unambiguously through CDGM catalogs in use'
 result={{'phase':{phase!r},'source_sha256':v['source_sha256'],'model_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),
  'available_catalogs':available,'catalogs_in_use':in_use,'elements':elements,'all_six_native_materials_CDGM':all_cdgm,
  'quotation_status':'No verified supplier quote, cost savings, availability, batch precision, cost or delivery commitment.'}}
 (R/'material_catalog_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 with (R/'material_comparison.csv').open('w',newline='',encoding='utf-8-sig') as f:
  writer=csv.DictWriter(f,fieldnames=list(elements[0]));writer.writeheader();writer.writerows(elements)
 print('Verified six native material/catalog identities; all CDGM:',all_cdgm,flush=True)
finally:app.CloseApplication()
'''


def freeze(folder, args):
    selection_path = folder / 'selection_frozen.json'
    frozen = folder / 'frozen_source.zmx'
    if selection_path.exists():
        selection = read(selection_path)
        if not frozen.exists() or sha(frozen) != selection['source_sha256']:
            raise RuntimeError('Frozen selection identity changed; refusing to silently replace it.')
        return selection
    candidate = folder / args.best
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    if frozen.exists() and sha(frozen) != sha(candidate):
        raise RuntimeError('Existing frozen source differs from selected best; review before replacing.')
    if candidate.resolve() != frozen.resolve():
        shutil.copy2(candidate, frozen)
    metrics = folder / args.metrics
    selection = {'phase': args.phase, 'selected_from': str(candidate), 'source_candidate': frozen.name,
                 'source_sha256': sha(frozen), 'frozen_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                 'selection_metrics_file': str(metrics) if metrics.exists() else None,
                 'selection_metrics_sha256': sha(metrics) if metrics.exists() else None,
                 'worker_budget': args.workers, 'actual_native_apps_at_once': 1,
                 'search_metrics_used_for_performance_certification': False}
    if metrics.exists():
        shutil.copy2(metrics, folder / 'selection_metrics_frozen.json')
    write(selection_path, selection)
    return selection


def run_stage(name, command, folder, state, selection):
    state_path = folder / 'finalization_state.json'
    state['stage'] = name
    state['status'] = 'running'
    state['updated_at_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    atomic_state(state_path, state)
    print('Finalization stage:', name, flush=True)
    with (folder / f'finalize_{name}.log').open('a', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=str(P), stdout=log, stderr=subprocess.STDOUT)
        state['child_pid'] = process.pid
        atomic_state(state_path, state)
        process.wait()
    state['child_pid'] = None
    if sha(folder / 'frozen_source.zmx') != selection['source_sha256']:
        raise RuntimeError('Frozen source changed during finalization.')
    if process.returncode:
        state['status'] = 'failed'
        state['failed_stage'] = name
        atomic_state(state_path, state)
        raise RuntimeError(f'{name} failed ({process.returncode}); see finalize_{name}.log')
    if name not in state['completed_stages']:
        state['completed_stages'].append(name)
    atomic_state(state_path, state)


def update_comparison():
    lines = ['# 夜间两方案对比 - 2026-09-15\n',
             '只对比已完成的独立原生结果；未经验证的另一阶段不推定达标。价格和供应未取得正式询价，不报告实测降本。\n',
             '| 方案 | 光圈 | 最大低于手册，百分点 | 严格达到下限 / 项数 | 冻结处方 |\n| --- | --- | ---: | ---: | --- |']
    details = []
    for phase, (code, label) in PHASES.items():
        folder = BASE / phase
        accepted = folder / 'acceptance.json'
        verified = folder / 'validated.json'
        if not accepted.exists() or not verified.exists():
            details.append(f'{label}：原生验收尚未完成。')
            continue
        a, v = read(accepted), read(verified)
        if a.get('source_sha256') != v.get('source_sha256'):
            details.append(f'{label}：验收身份错配，不引用数值。')
            continue
        for fn, metric in a['per_aperture'].items():
            lines.append(f"| {label} | f/{fn} | {100*metric['max_shortfall']:.3f} | {metric['points_at_or_above_reference']} / {metric['points']} | {v['source_sha256'][:12]} |")
        materials_path = folder / 'material_catalog_audit.json'
        materials = read(materials_path) if materials_path.exists() else None
        if materials and materials.get('source_sha256') == v['source_sha256']:
            details.append(label + '六片：' + '；'.join(f"L{row['element']} {row['historical_reference_glass']} -> {row['native_material']}" for row in materials['elements']) + '。')
        details.append(f"{label}：完整全视场 {v['full_field_deg']:.1f}°；共同像面 {v['common_image_distance_mm']:.8f} mm；非球面只含 A4/A6。")
    lines.extend(['\n' + text + '\n' for text in details])
    lines.append('\nMTF 图为 FFT512 完整视场曲线，定量 f/5.6 为 FFT1024，其它光圈为 FFT512。手册为人工数字化折线，不是原厂原始数值；独立方法、真实像高、公差与样机验证缺口见各方案报告。\n')
    BASE.mkdir(parents=True, exist_ok=True)
    (BASE / '两方案对比.md').write_text('\n'.join(lines), encoding='utf-8')


def build_catalog_tradeoff(folder):
    """Read stopped-search snapshots, never optimize or infer delivered prices."""
    v = read(folder / 'validated.json')
    material = read(folder / 'material_catalog_audit.json')
    audit = {'source_sha256': v['source_sha256'], 'selected_cost_proxy_verified': False,
             'selected_elements': [], 'display_candidates': [], 'reasons': [],
             'cost_scope': 'Within one frozen CDGM catalog only; OD[0] six-element unweighted sum, not a quote.',
             'absolute_price_RMB': None, 'cross_catalog_savings_percent': None,
             'other_candidate_high_sampling_verified': False}
    manifest_path, plan_path = BASE / 'material_manifest.json', BASE / 'catalog_plan.json'
    if material.get('source_sha256') != v['source_sha256'] or not material.get('all_six_native_materials_CDGM'):
        audit['reasons'].append('最终六片原生 CDGM 材料身份未完成。')
        return audit
    if not manifest_path.exists() or not plan_path.exists():
        audit['reasons'].append('material_manifest.json 或 catalog_plan.json 缺失。')
        return audit
    manifest, plan = read(manifest_path), read(plan_path)
    manifest_hash, plan_hash = sha(manifest_path), sha(plan_path)
    audit['material_manifest_sha256'], audit['catalog_plan_sha256'] = manifest_hash, plan_hash
    snapshots = [row for row in manifest.get('catalog_snapshots', []) if row['catalog'].upper() == 'CDGM']
    plan_snapshots = [row for row in plan.get('catalog_snapshots', []) if row['catalog'].upper() == 'CDGM']
    if len(snapshots) != 1 or len(plan_snapshots) != 1 or snapshots[0]['sha256'] != plan_snapshots[0]['sha256']:
        audit['reasons'].append('manifest 与 plan 的 CDGM 目录 snapshot 身份不一致。')
        return audit
    snapshot = snapshots[0]
    snapshot_path = (BASE / snapshot['snapshot']).resolve()
    if not snapshot_path.is_relative_to(BASE.resolve()) or not snapshot_path.exists() or sha(snapshot_path) != snapshot['sha256']:
        audit['reasons'].append('冻结 CDGM AGF snapshot 不存在或 hash 错配。')
        return audit
    audit['CDGM_catalog_sha256'], audit['CDGM_catalog_header'] = snapshot['sha256'], snapshot.get('header', '日期未记录')

    def costs(materials):
        entries = [manifest.get('materials', {}).get('CDGM:' + name) for name in materials]
        if len(entries) != 6 or any(row is None for row in entries):
            return None
        values = []
        for row in entries:
            od = row.get('OD', [])
            value = row.get('catalog_relative_cost')
            if not od or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0 or abs(float(od[0]) - value) > 1e-8:
                return None
            values.append(float(value))
        return values

    selected_names = [row['native_material'] for row in material['elements']]
    selected_costs = costs(selected_names)
    if selected_costs is None:
        audit['reasons'].append('选定材料缺失正值 OD 第一项或 manifest 代理不一致。')
        return audit
    for row, value in zip(material['elements'], selected_costs):
        entry = manifest['materials']['CDGM:' + row['native_material']]
        audit['selected_elements'].append({'element': row['element'], 'surface': row['surface'],
                    'historical_reference_glass': row['historical_reference_glass'], 'native_material': row['native_material'],
                    'catalog_relative_cost': value, 'OD_raw': entry.get('OD_raw'),
                    'nd_catalog': entry.get('nd_catalog'), 'vd_catalog': entry.get('vd_catalog'),
                    'availability_verified': False, 'price_quote_available': False})
    records = []
    pareto_path = folder / 'candidate_pareto.json'
    pareto = read(pareto_path) if pareto_path.exists() else None
    if pareto is None:
        audit['reasons'].append('candidate_pareto.json 缺失，不能确认搜索候选 Pareto 汇总。')
    else:
        audit['candidate_pareto_sha256'] = sha(pareto_path)
        records.extend(pareto.get('all_feasible_combo_bests', []))
    pointers = sorted((folder / 'combo_bests').glob('*/best.json'))
    audit['combo_best_pointer_sha256'] = {str(path.relative_to(folder)): sha(path) for path in pointers}
    if not pointers:
        audit['reasons'].append('combo_bests 缺失或没有组合 best，不能报告其它便宜候选已筛选可行。')
    full = []
    for path in pointers + ([folder / 'best.json'] if (folder / 'best.json').exists() else []):
        full.append(read(path))
    full_by_sha = {row.get('source_sha256'): row for row in full}
    records.extend(full)
    eligible = {}
    for partial in records:
        record = full_by_sha.get(partial.get('source_sha256'), partial)
        source = Path(record.get('source_path', ''))
        if not source.is_absolute():
            source = folder / source
        if not source.resolve().is_relative_to(folder.resolve()) or not source.is_file() or sha(source) != record.get('source_sha256'):
            audit['reasons'].append('有优化筛选候选 snapshot 身份未核对，已排除。')
            continue
        if record.get('feasible') is not True or record.get('catalog_plan_sha256') != plan_hash:
            continue
        combo = record.get('material_combo', {})
        names = record.get('materials', combo.get('materials', []))
        catalogs = record.get('catalogs', combo.get('catalogs', []))
        values = costs(names)
        proxy = record.get('cdgm_cost_proxy', {})
        if values is None or len(catalogs) != 6 or any(name.upper() != 'CDGM' for name in catalogs) or proxy.get('manifest_sha256') != manifest_hash:
            continue
        total = sum(values)
        recorded_total = proxy.get('sum_six_element_relative_cost')
        if not proxy.get('eligible') or recorded_total is None or abs(recorded_total - total) > 1e-8:
            continue
        score, deficit = record.get('score'), record.get('max_shortfall')
        if not isinstance(score, (int, float)) or not isinstance(deficit, (int, float)) or not math.isfinite(score) or not math.isfinite(deficit):
            continue
        key = record['source_sha256']
        eligible[key] = {'source_sha256': key, 'materials': names, 'catalogs': catalogs,
                         'sum_six_element_relative_cost': total, 'screening_score': score,
                         'screening_max_shortfall': deficit, 'screening_sampling': record.get('sampling', '未记录'),
                         'is_selected_source': key == v['source_sha256'], 'snapshot_path': str(source),
                         'independent_high_sampling_verified': key == v['source_sha256']}
    selected_record = eligible.get(v['source_sha256'])
    if selected_record is None or selected_record['materials'] != selected_names:
        audit['reasons'].append('最终冻结来源未与 combo best/plan/manifest 筛选记录闭合，选定 OD 及其它成本候选不作为已核验结果。')
        audit['selected_elements'] = []
        return audit
    audit['selected_cost_proxy_verified'] = True
    audit['selected_sum_six_element_relative_cost'] = sum(selected_costs)
    items = list(eligible.values())
    frontier = [row for row in items if not any(other['screening_score'] <= row['screening_score'] and other['sum_six_element_relative_cost'] <= row['sum_six_element_relative_cost'] and (other['screening_score'] < row['screening_score'] or other['sum_six_element_relative_cost'] < row['sum_six_element_relative_cost']) for other in items)]
    cheapest = min(items, key=lambda row: (row['sum_six_element_relative_cost'], row['screening_score']))
    optical = min(items, key=lambda row: row['screening_score'])
    displayed = {}
    for label, row in [('正式选定', selected_record), ('最低目录代理筛选可行', cheapest), ('最低光学筛选分数', optical)] + [('筛选 Pareto', row) for row in sorted(frontier, key=lambda row: row['sum_six_element_relative_cost'])[:6]]:
        key = row['source_sha256']
        if key in displayed:
            displayed[key]['label'] += ' / ' + label
        else:
            displayed[key] = dict(row, label=label)
    audit['display_candidates'] = list(displayed.values())
    audit['authenticated_screening_candidate_count'] = len(items)
    audit['all_authenticated_candidates'] = items
    cheaper = [row for row in items if row['sum_six_element_relative_cost'] < sum(selected_costs) - 1e-8]
    audit['tradeoff_interpretation'] = (
        f"本次可核对 {len(items)} 个全 CDGM 优化筛选组合；其中 {len(cheaper)} 个目录 OD 合计低于正式选定组合。"
        + (f"最低代理为 {cheapest['sum_six_element_relative_cost']:.4f}，其筛选最大 MTF 不足为 {100*cheapest['screening_max_shortfall']:.3f} 个百分点，非本方案的独立高采样结果。" if cheaper else '目前没有已核对的更低 OD 筛选组合，不能据此证明该选型在所有材料和加工方案中最便宜。')
        + ' 光学筛选分数为最大短缺+0.2×短缺RMS；它不是毛坯成本或量产目标。Pareto 仅针对本次已搜索、同目录代理和筛选光学分数，范围有限。正式选定方案的高采样结果由主验收表提供，不能把其它组合的筛选值混入其中。')
    audit['reasons'] = list(dict.fromkeys(audit['reasons']))
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=PHASES, required=True)
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--best', default='best.zmx')
    parser.add_argument('--metrics', default='best_metrics.json')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--prepare-only', action='store_true', help='Native validation/curves/mapping/manufacturing; no PDF (default).')
    modes.add_argument('--author-only', action='store_true', help='Only author this scheme PDF after caller has run the PDF skill marker.')
    modes.add_argument('--stage-scripts-only', action='store_true', help='Create/compile isolated stage scripts only; no native app or PDF.')
    parser.add_argument('--pdf-marker-confirmed', action='store_true', help='Optional caller attestation that its PDF skill marker succeeded; script does not execute a marker.')
    parser.add_argument('--skip-mapping', action='store_true')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.workers <= (2 if args.phase == 'general' else 8):
        parser.error('general budget must be 1-2; CDGM budget must be 1-8.')
    folder = (BASE / args.phase).resolve()
    if not folder.is_relative_to(P.resolve()):
        raise RuntimeError('Phase folder must stay under SuperSymmarXL.')
    folder.mkdir(parents=True, exist_ok=True)
    for name in [args.best, args.metrics]:
        if not (folder / name).resolve().is_relative_to(folder):
            parser.error('--best/--metrics must stay within this phase folder.')
    pipeline = prepare(args.phase, folder)
    if args.stage_scripts_only:
        print('Prepared isolated pipeline; no native app or PDF has been opened.', flush=True)
        return
    selection = freeze(folder, args)
    state_path = folder / 'finalization_state.json'
    state = read(state_path) if (args.resume or args.author_only) and state_path.exists() else {'phase': args.phase, 'source_sha256': selection['source_sha256'], 'completed_stages': []}
    if state.get('source_sha256') != selection['source_sha256']:
        raise RuntimeError('Resume state refers to another frozen source.')
    state['finalizer_pid'] = os.getpid()
    code = PHASES[args.phase][0]
    official = f'SuperSymmarXL_150_{code}_f5p6.zmx'
    stages = [('validate', [sys.executable, str(pipeline / 'validate.py'), '--input', 'frozen_source.zmx']),
              ('integrity', [sys.executable, str(pipeline / 'integrity.py')]),
              ('materials', [sys.executable, str(pipeline / 'materials.py')]),
              ('curve', [sys.executable, str(pipeline / 'curve.py'), '--input', official]),
              ('manufacturing', [sys.executable, str(pipeline / 'manufacturing.py')])]
    if not args.skip_mapping:
        stages.append(('mapping', [sys.executable, str(pipeline / 'mapping.py'), '--model', str(folder / official)]))
    if args.author_only:
        required = ['validated.json', 'field_curves.json', 'final_integrity.json',
                    'manufacturing_geometry_metrics.json', 'material_catalog_audit.json']
        for filename in required:
            if not (folder / filename).is_file():
                raise RuntimeError(f'Author-only requires completed native preparation: missing {filename}.')
        validated = read(folder / 'validated.json')
        if validated.get('source_sha256') != selection['source_sha256']:
            raise RuntimeError('Author-only validated identity differs from the frozen selection.')
        for filename in ['field_curves.json', 'manufacturing_geometry_metrics.json', 'material_catalog_audit.json']:
            if read(folder / filename).get('source_sha256') != selection['source_sha256']:
                raise RuntimeError(f'Author-only rejects stale {filename}.')
        for filename, expected in validated['official_file_sha256'].items():
            if sha(folder / filename) != expected:
                raise RuntimeError(f'Author-only official model identity changed: {filename}.')
        material = read(folder / 'material_catalog_audit.json')
        if args.phase == 'cdgm' and not material.get('all_six_native_materials_CDGM'):
            raise RuntimeError('Author-only CDGM material audit has not confirmed six CDGM materials.')
        if args.phase == 'cdgm':
            write(folder / 'catalog_tradeoff_audit.json', build_catalog_tradeoff(folder))
        state['PDF_marker_responsibility'] = 'Caller must successfully run create/count2 marker exactly once before the first of the two scheme reports.'
        state['PDF_marker_caller_attested'] = bool(args.pdf_marker_confirmed)
        stages = [('report', [sys.executable, str(pipeline / 'report.py')])]
    for name, command in stages:
        if args.resume and name in state['completed_stages']:
            continue
        run_stage(name, command, folder, state, selection)
    state.pop('failed_stage', None)
    state['status'] = 'authored_pending_visual_QA' if args.author_only else 'native_validated_pending_report_authoring'
    state['native_apps_at_once'] = 1
    state['PDF_visual_QA_completed'] = False
    atomic_state(state_path, state)
    update_comparison()
    print('Finished', args.phase, state['status'], 'at', folder, flush=True)
    if args.author_only:
        print('Render and inspect every PDF page before delivery; this script does not certify visual QA.', flush=True)


if __name__ == '__main__':
    main()
