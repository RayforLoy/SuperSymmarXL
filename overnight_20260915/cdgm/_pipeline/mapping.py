"""Read-only native ZOS audit. Independent standalone app within the supervisor concurrency budget.

No ZMX is saved. Audits chief-ray image mapping, geometric clear-pupil
survival, native relative illumination and the manufacturer's focusing rule.
Default grid is 41x41 in the unit disk; these fractions are geometric pupil
area, NOT radiometric illumination or manufacturing yield.
"""
from pathlib import Path
import argparse
import collections
import json
import math
import hashlib
import numpy as np

P = Path('D:\\_Camera\\LensRebuild\\SuperSymmarXL')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model', type=Path, default=Path('D:\\_Camera\\LensRebuild\\SuperSymmarXL\\overnight_20260915\\cdgm\\SuperSymmarXL_150_CDGM_f5p6.zmx'))
parser.add_argument('--grid', type=int, default=41)
parser.add_argument('--focus-span', type=float, default=0.2)
parser.add_argument('--focus-points', type=int, default=41)
args = parser.parse_args()
if not args.model.is_file():
    raise FileNotFoundError(args.model)
if args.grid < 5 or args.focus_points < 5:
    raise ValueError('Grid and focus scan need at least 5 samples per axis.')
R = Path('D:\\_Camera\\LensRebuild\\SuperSymmarXL\\overnight_20260915\\cdgm')
validated=json.loads((R/'validated.json').read_text(encoding='utf-8'))
model_hash=hashlib.sha256(args.model.read_bytes()).hexdigest()
assert model_hash==validated['official_file_sha256'][args.model.name], 'Model identity mismatch'
target = json.loads((R/'target_optimization.json').read_text(encoding='utf-8'))
height_lists = target.get('heights_by_aperture', {})
if height_lists:
    heights = sorted({float(h) for hs in height_lists.values() for h in hs})
else:
    heights = sorted(set(map(float, target['heights'])))
# Include complete field even when a particular aperture has a shorter factory
# MTF curve. These added diagnostic points are not invented reference values.
heights = sorted(set(heights + [0.0, 1.0]))
# Existing bootstrap makes one standalone native instance; never invoked on import elsewhere.
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
report = {'model': str(args.model.resolve()), 'model_sha256':model_hash,'source_sha256':validated['source_sha256'],'read_only_zmx': True,
          'target_file': 'target_optimization.json', 'diagnostic_heights_union': heights,
          'methods': {'chief_ray': 'native normalized unpolarized real ray, px=py=0; cross-check REAY',
                      'pupil': 'uniform Cartesian grid in normalized entrance-pupil unit disk, six wavelengths; success requires ErrorCode=0 and vignetteCode=0',
                      'radiometry': 'native relative illumination analysis; not inferred from pupil fraction',
                      'focus': 'polychromatic axis FFT MTF at 20 lp/mm, f/5.6, 256 sampling; scan only, no official file changes'},
          'warnings': []}

def read_results(data):
    """pythonnet normally omits pure out args; retain an explicit-zero fallback."""
    if not data.StartReadingResults():
        raise RuntimeError('Native ray data has no readable results.')
    rows = []
    while True:
        try:
            row = data.ReadNextResult()
        except TypeError:
            row = data.ReadNextResult(0, 0, 0, *([0.0]*11))
        row = tuple(row)
        # Reflected native contract: bool return + 14 out values.
        if len(row) != 15:
            raise RuntimeError('Unexpected ReadNextResult tuple: ' + repr(row))
        if not row[0]:
            break
        rows.append({'ray_number': int(row[1]), 'error': int(row[2]),
                     'vignette_surface': int(row[3]), 'x': float(row[4]),
                     'y': float(row[5]), 'z': float(row[6]),
                     'l': float(row[7]), 'm': float(row[8]), 'n': float(row[9]),
                     'intensity': float(row[14])})
    return rows

def ray_batch(ray_specs, to_surface):
    tool = sys.Tools.OpenBatchRayTrace()
    try:
        data = tool.CreateNormUnpol(len(ray_specs), Z.Tools.RayTrace.RaysType.Real, to_surface)
        for wave, hx, hy, px, py in ray_specs:
            if not data.AddRay(wave, hx, hy, px, py, getattr(Z.Tools.RayTrace.OPDMode, 'None')):
                raise RuntimeError('Native AddRay failed.')
        tool.RunAndWaitForCompletion()
        rows = read_results(data)
        if len(rows) != len(ray_specs):
            raise RuntimeError(f'Expected {len(ray_specs)} rays; returned {len(rows)}.')
        return rows
    finally:
        tool.Close()

try:
    sys.LoadFile(str(args.model.resolve()), False)
    image_surface = sys.LDE.NumberOfSurfaces - 1
    last_surface = image_surface - 1
    last = sys.LDE.GetSurfaceAt(last_surface)
    official_focus = float(last.Thickness)
    sd = sys.SystemData
    field_type = str(sd.Fields.GetFieldType())
    if field_type != 'Angle':
        raise ValueError('This audit currently assumes Angle fields: ' + field_type)
    max_field = max(math.hypot(sd.Fields.GetField(i).X, sd.Fields.GetField(i).Y)
                    for i in range(1, sd.Fields.NumberOfFields+1))
    if abs(max_field-52.5) > 1e-6:
        raise ValueError('Expected full 105 degree field; found ' + str(max_field*2))
    waves = [(i, float(sd.Wavelengths.GetWavelength(i).Weight))
             for i in range(1, sd.Wavelengths.NumberOfWavelengths+1)]
    norm_weight = sum(w for _, w in waves)
    grid = np.linspace(-1.0, 1.0, args.grid)
    disk = [(float(px), float(py)) for py in grid for px in grid if px*px+py*py <= 1.0+1e-12]
    report.update({'image_surface': image_surface, 'last_optical_surface': last_surface,
                   'official_image_distance_mm': official_focus, 'field_type': field_type,
                   'full_field_deg': max_field*2, 'grid_samples_per_wavelength': len(disk),
                   'wavelength_count': len(waves), 'apertures': {}})
    # Explicit same entrance pupil convention as the existing CDGM evaluator.
    for fn in [5.6, 8.0, 22.0]:
        key = str(fn).removesuffix('.0')
        sd.Aperture.ApertureValue = 148.1/fn
        entries = []
        for h in heights:
            angle = 52.5 if h == 1 else math.degrees(math.atan(193*h/148.1))
            hy = angle/max_field
            chief = ray_batch([(i, 0, hy, 0, 0) for i, _ in waves], image_surface)
            reay = float(sys.MFE.GetOperandValue(Z.Editors.MFE.MeritOperandType.REAY,
                                                image_surface, 1, 0, hy, 0, 0, 0, 0))
            specs = [(i, 0, hy, px, py) for i, _ in waves for px, py in disk]
            traced = ray_batch(specs, image_surface)
            chromatic = []
            for k, (wave, weight) in enumerate(waves):
                rows = traced[k*len(disk):(k+1)*len(disk)]
                passed = sum(x['error']==0 and x['vignette_surface']==0 for x in rows)
                errors = collections.Counter(str(x['error']) for x in rows if x['error']!=0)
                blocked = collections.Counter(str(x['vignette_surface']) for x in rows if x['vignette_surface']!=0)
                chromatic.append({'wavelength_number': wave, 'weight': weight,
                                  'passed_rays': passed, 'fraction': passed/len(disk),
                                  'error_codes': dict(errors), 'vignette_surfaces': dict(blocked)})
            weighted = sum(x['weight']*x['fraction'] for x in chromatic)/norm_weight
            published_hs = height_lists.get(key, target.get('heights', [])[:len(target['data'][key])])
            entries.append({'reference_height_fraction': h, 'configured_angle_deg': angle,
                            'is_published_reference_height_for_aperture': any(abs(h-float(x))<1e-9 for x in published_hs),
                            'normalized_field_hy': hy, 'primary_chief_y_mm': chief[0]['y'],
                            'actual_primary_height_fraction': abs(chief[0]['y'])/193,
                            'height_mapping_error_mm': chief[0]['y']-193*h,
                            'distortion_relative_to_reference_pct': 100*(chief[0]['y']/(193*h)-1) if h else 0,
                            'REAY_primary_y_mm': reay, 'batch_minus_REAY_mm': chief[0]['y']-reay,
                            'chief_by_wavelength': chief, 'weighted_geometric_pupil_fraction': weighted,
                            'pupil_by_wavelength': chromatic})
            print('audit', key, h, 'image y', round(chief[0]['y'], 6), 'pupil fraction', round(weighted, 4), flush=True)
        axis_fraction = entries[0]['weighted_geometric_pupil_fraction']
        for x in entries:
            x['relative_geometric_pupil_fraction_to_axis'] = x['weighted_geometric_pupil_fraction']/axis_fraction if axis_fraction else None
        aperture = {'fields': entries}
        # Native radiometric analysis gives a separate check including obliquity.
        try:
            analysis = sys.Analyses.New_RelativeIllumination()
            try:
                settings = Z.Analysis.Settings.ExtendedScene.IAS_RelativeIllumination(analysis.GetSettings())
                settings.FieldDensity = 21
                settings.RayDensity = args.grid
                settings.ScanType = Z.Analysis.Settings.ScanTypes.Plus_Y
                settings.RemoveVignettingFactors = False
                analysis.ApplyAndWaitForCompletion()
                results = analysis.GetResults()
                native_path = R/('audit_relative_illumination_f'+key+'.txt')
                results.GetTextFile(str(native_path))
                series = []
                for i in range(results.NumberOfDataSeries):
                    d = results.GetDataSeries(i)
                    yy = np.array(list(d.YData.Data)).reshape(d.YData.Data.GetLength(0), -1)
                    series.append({'x': [float(v) for v in d.XData.Data], 'y': yy.tolist()})
                aperture['native_relative_illumination'] = {'raw_text_file': str(native_path), 'series': series}
            finally:
                analysis.Close()
        except Exception as exc:
            report['warnings'].append('Native relative illumination unavailable for f/'+key+': '+str(exc))
        report['apertures'][key] = aperture
    # Source focus rule: find axis maximum at 20lp f/5.6, hold other properties fixed.
    sd.Aperture.ApertureValue = 148.1/5.6
    mtf = sys.Analyses.New_FftMtf()
    try:
        settings = Z.Analysis.Settings.Mtf.IAS_FftMtf(mtf.GetSettings())
        settings.MaximumFrequency = 20
        settings.SampleSize = Z.Analysis.SampleSizes.S_256x256
        settings.Field.SetFieldNumber(1)
        settings.Wavelength.UseAllWavelengths()
        scan = []
        for offset in np.linspace(-args.focus_span, args.focus_span, args.focus_points):
            last.Thickness = official_focus+float(offset)
            mtf.ApplyAndWaitForCompletion()
            data = mtf.GetResults().GetDataSeries(0)
            xx = np.asarray(list(data.XData.Data), dtype=float)
            yy = np.asarray(list(data.YData.Data), dtype=float).reshape(data.YData.Data.GetLength(0), -1)
            axis20 = [float(np.interp(20, xx, yy[:,j])) for j in [0,1]]
            scan.append({'image_distance_offset_mm': float(offset), 'axis_20_T_S': axis20,
                         'mean_axis_20_mtf': sum(axis20)/2})
        best = max(range(len(scan)), key=lambda i: scan[i]['mean_axis_20_mtf'])
        report['focus_scan'] = {'sampling': 256, 'scan': scan, 'best_grid_sample': scan[best],
                                'peak_at_scan_boundary': best in [0, len(scan)-1],
                                'official_plane_mtf': min(scan, key=lambda x: abs(x['image_distance_offset_mm']))}
        if best in [0, len(scan)-1]:
            report['warnings'].append('Focus peak at scan boundary; enlarge --focus-span before interpreting optimum.')
    finally:
        last.Thickness = official_focus
        mtf.Close()
    (R/'mapping_pupil_focus_audit.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print('Audit written; official ZMX untouched.', flush=True)
finally:
    app.CloseApplication()
