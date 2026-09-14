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
 names={{catalog:set(map(str,catalogs.GetMaterialsInCatalog(catalog))) for catalog in in_use}}
 cdgm_catalogs=[catalog for catalog in available if catalog.upper()=='CDGM']
 cdgm_names=set()
 for catalog in cdgm_catalogs:cdgm_names.update(map(str,catalogs.GetMaterialsInCatalog(catalog)))
 historical=json.loads((ROOT/'revision2'/'validated.json').read_text(encoding='utf-8'))
 previous={{int(s['surface']):s['glass'] for s in historical['surfaces']}}
 elements=[]
 for element,i in enumerate([1,3,5,8,9,11],1):
  material=str(sys.LDE.GetSurfaceAt(i).Material)
  solve=str(sys.LDE.GetSurfaceAt(i).MaterialCell.GetSolveData().Type)
  assert solve in ['Fixed','None'],'Material must resolve through a fixed catalog, not a model/offset/substitution solve'
  containing=[catalog for catalog in in_use if material in names[catalog]]
  elements.append({{'element':element,'surface':i,'historical_reference_glass':previous[i],
   'native_material':material,'native_material_solve':solve,'catalogs_in_use_containing_material':containing,
   'member_of_available_CDGM_catalog':material in cdgm_names,
   'unambiguous_CDGM_resolution':bool(containing) and all(c.upper()=='CDGM' for c in containing)}})
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
        state['PDF_marker_responsibility'] = 'Caller must successfully run create/count2 marker exactly once before the first of the two scheme reports.'
        state['PDF_marker_caller_attested'] = bool(args.pdf_marker_confirmed)
        stages = [('report', [sys.executable, str(pipeline / 'report.py')])]
    for name, command in stages:
        if args.resume and name in state['completed_stages']:
            continue
        run_stage(name, command, folder, state, selection)
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
