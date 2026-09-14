"""Deadline-bounded native A6 shape and discrete catalog-glass search.

One process pool owns all native applications. Immutable best snapshots are
written immediately; best.json is only a pointer. No canonical files are edited.
"""
from pathlib import Path
import argparse, datetime as dt, hashlib, json, os, time, random
import multiprocessing as mp
from multiprocessing.util import Finalize
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from numpy.polynomial import Polynomial, Legendre
from scipy.optimize import least_squares
import optimize_revision3 as core

BASE = core.ROOT / 'overnight_20260915'
SURFACES = [1, 3, 5, 8, 9, 11]
FO_TARGET = np.array([148.1, 135.9, 36.6, 77.416])
GAP_LIMITS = np.array([.7, .3, 1., .3, .7, 1., .7, .3, .7])
ORIGINAL_GEOMETRY = core.geometry
class DeadlineReached(RuntimeError): pass
class RoundExpired(RuntimeError): pass

def atomic_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temporary, path)

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def combo_key(combo):
    return hashlib.sha256(json.dumps(list(zip(combo['catalogs'], combo['materials']))).encode()).hexdigest()[:16]

def record_feasible(record):
    return bool(not record['invalid_geometry'] and
                np.all(abs(np.array(record['first_order'])-FO_TARGET) < [.25, .4, .5, .6]) and
                record.get('stop_crossing_air_gap_S6_to_S8_mm', .3) >= .3)

def pure_first_order(radii, thickness, indices):
    """Reduced-angle matrix, using actual resolved primary-wavelength INDX."""
    matrix = np.eye(2); old = 1.; entry = 0.
    for i in range(1, 13):
        n = float(indices[i-1]); radius = radii[i-1]
        power = 0. if not np.isfinite(radius) else -(n-old)/radius
        matrix = np.array([[1., 0.], [power, 1.]]) @ matrix
        if i == 7: entry = matrix[0, 1]/matrix[0, 0]
        if i < 12: matrix = np.array([[1., thickness[i-1]/n], [0., 1.]]) @ matrix
        old = n
    return [-1/matrix[1, 0], -matrix[0, 0]/matrix[1, 0], entry, float(sum(thickness))]

def pure_geometry(radii, thickness, coefficients, caps):
    def sag(i, r):
        radius = radii[i-1]
        if not np.isfinite(radius): return np.zeros_like(r)
        if max(r) >= abs(radius): return np.full_like(r, np.nan)
        value = r*r/(radius*(1+np.sqrt(1-(r/radius)**2)))
        if i == 10: value += coefficients[0]*r**4 + coefficients[1]*r**6
        return value
    gaps = []
    for i in [1, 2, 3, 4, 5, 8, 9, 10, 11]:
        radius = 15.8 if i == 10 else min(caps[i], caps[i+1])
        r = np.linspace(0, radius, 301)
        values = thickness[i-1]+sag(i+1, r)-sag(i, r)
        gaps.append(float(min(values)) if np.all(np.isfinite(values)) else -100.)
    r = np.linspace(0, min(caps[6], caps[8]), 301)
    values = thickness[5]+thickness[6]+sag(8, r)-sag(6, r)
    stop_gap = float(min(values)) if np.all(np.isfinite(values)) else -100.
    return gaps, stop_gap

def precondition_bounds():
    low = np.r_[[-3.]*11, [-2.]*11]; low[17] = -2.5
    return low, -low

def solve_fo_precondition(radii, thickness, coefficients, indices, caps, check=lambda: None):
    """Pure 22-variable correction; no material equivalence or native FFT."""
    radii = np.asarray(radii, float); thickness = np.asarray(thickness, float)
    rbase = radii[np.array(core.RIDS)-1].copy()
    def state(z):
        rr = radii.copy(); rr[np.array(core.RIDS)-1] = rbase*(1+np.asarray(z[:11])*.03)
        tt = thickness+np.asarray(z[11:])*.35
        fo = np.array(pure_first_order(rr, tt, indices))
        gaps, stop = pure_geometry(rr, tt, coefficients, caps)
        return fo, np.array(gaps), stop
    def objective(z):
        check(); fo, gaps, stop = state(z)
        return np.r_[(fo-FO_TARGET)*[3., 3., 2., 2.],
                     np.maximum(GAP_LIMITS-gaps, 0)*10., max(0, .3-stop)*10., np.asarray(z)*.001]
    before_fo, before_gaps, before_stop = state(np.zeros(22))
    low, high = precondition_bounds()
    result = least_squares(objective, np.zeros(22), bounds=(low, high), max_nfev=50,
                           ftol=1e-9, xtol=1e-9, gtol=1e-9)
    after_fo, after_gaps, after_stop = state(result.x)
    feasible = bool(np.all(abs(after_fo-FO_TARGET) < [.25, .4, .5, .6]) and
                    np.all(after_gaps >= GAP_LIMITS) and after_stop >= .3)
    x0 = np.r_[np.zeros(2), result.x]
    metadata = {'enabled': True, 'method': 'Pure reduced-angle FO from resolved native INDX; no FFT',
                'primary_wavelength_um': .546, 'primary_indices_surfaces_1_to_12': list(map(float, indices)),
                'before_first_order': before_fo.tolist(), 'after_first_order': after_fo.tolist(),
                'before_geometry_gaps': before_gaps.tolist(), 'after_geometry_gaps': after_gaps.tolist(),
                'before_stop_crossing_air_gap_mm': before_stop, 'after_stop_crossing_air_gap_mm': after_stop,
                'feasible': feasible, 'x0': x0.tolist(), 'nfev': int(result.nfev), 'status': str(result.message),
                'asphere_parameter_changes': [0., 0.], 'parameter_bounds_low': low.tolist(),
                'parameter_bounds_high': high.tolist()}
    return x0.tolist(), metadata

def cost_proxy(combo):
    """Unweighted six-element OD sum: CDGM internal ranking, never a quote."""
    path = BASE/'material_manifest.json'
    if not path.exists(): return {'eligible': False, 'reason': 'manifest unavailable'}
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if not all(c.upper() == 'CDGM' for c in combo['catalogs']):
        return {'eligible': False, 'reason': 'all-six-CDGM comparison only', 'manifest_sha256': digest(path)}
    values = [manifest['materials'].get('CDGM:'+name, {}).get('catalog_relative_cost') for name in combo['materials']]
    valid = all(v is not None and v > 0 for v in values)
    return {'eligible': valid, 'catalog': 'CDGM', 'element_catalog_relative_cost': values,
            'sum_six_element_relative_cost': float(sum(values)) if valid else None,
            'method': 'Unweighted sum of six frozen-CDGM AGF OD relative costs; same catalog only',
            'delivered_price': 'not_quoted', 'savings_percent': None, 'manifest_sha256': digest(path)}

def write_pareto(out, combo_bests):
    entries = [{'combo_key': key, 'score': value['score'], 'max_shortfall': value['max_shortfall'],
                'deficit_rms': value['deficit_rms'], 'source_path': value['source_path'],
                'source_sha256': value['source_sha256'], 'materials': value['materials'],
                'catalogs': value['catalogs'], 'cdgm_cost_proxy': value.get('cdgm_cost_proxy', {})}
               for key, value in combo_bests.items()]
    eligible = [e for e in entries if e['cdgm_cost_proxy'].get('eligible')]
    pareto = []
    for e in eligible:
        ec = e['cdgm_cost_proxy']['sum_six_element_relative_cost']
        dominated = any(q['score'] <= e['score'] and q['cdgm_cost_proxy']['sum_six_element_relative_cost'] <= ec and
                        (q['score'] < e['score'] or q['cdgm_cost_proxy']['sum_six_element_relative_cost'] < ec) for q in eligible)
        if not dominated: pareto.append(e)
    atomic_json(out/'candidate_pareto.json', {'all_feasible_combo_bests': entries, 'cdgm_pareto': pareto,
                'cost_scope': 'Frozen CDGM catalog internal OD ranking; no cross-manufacturer savings or delivered-price claim'})

def guard():
    now = time.time()
    if now >= HARD_END - GUARD_SECONDS: raise DeadlineReached('Phase closing margin reached')
    if now >= ROUND_END: raise RoundExpired('Round wall-clock budget reached')

def close_native():
    try: core.analysis.Close()
    except Exception: pass
    try: core.app.CloseApplication()
    except Exception: pass
    try:
        atomic_json(core.R/'workers'/str(os.getpid())/'native.json',
                    {'pid': os.getpid(), 'state': 'closed', 'closed_utc': dt.datetime.now(dt.timezone.utc).isoformat()})
    except Exception: pass

class GuardedAnalysis:
    def __init__(self, underlying): self.underlying = underlying
    def ApplyAndWaitForCompletion(self):
        guard(); return self.underlying.ApplyAndWaitForCompletion()
    def __getattr__(self, name): return getattr(self.underlying, name)

class GuardedMFE:
    def __init__(self, underlying): self.underlying = underlying
    def GetOperandValue(self, *args): guard(); return self.underlying.GetOperandValue(*args)
    def __getattr__(self, name): return getattr(self.underlying, name)

class GuardedSystem:
    def __init__(self, underlying): self.underlying = underlying; self.MFE = GuardedMFE(underlying.MFE)
    def SaveAs(self, path): guard(); return self.underlying.SaveAs(path)
    def __getattr__(self, name): return getattr(self.underlying, name)

def initialize(seed, target, phase, deadline, margin):
    global HARD_END, ROUND_END, GUARD_SECONDS, ACTIVE_KEY, RAW_SYSTEM, NATIVE_MATERIALS, NATIVE_N6
    HARD_END, ROUND_END, GUARD_SECONDS = deadline, float('inf'), margin
    guard()
    core.R = BASE / phase
    Finalize(None, close_native, exitpriority=10)
    core.initialize(seed, 128, target, False, True)
    guard()
    RAW_SYSTEM = core.sys; core.sys = GuardedSystem(RAW_SYSTEM)
    core.analysis = GuardedAnalysis(core.analysis)
    core.POWERS = np.array([4, 6]); core.NORM = 15.5
    ACTIVE_KEY = None; NATIVE_MATERIALS = []; NATIVE_N6 = []
    atomic_json(BASE / phase / 'workers' / str(os.getpid()) / 'native.json',
                {'pid': os.getpid(), 'started_utc': dt.datetime.now(dt.timezone.utc).isoformat()})

def prepare(seed, combo, size):
    global ACTIVE_KEY, BASE_B, NATIVE_MATERIALS, NATIVE_N6
    key = (seed, tuple(combo['materials']), tuple(combo['catalogs']), size)
    if key == ACTIVE_KEY: return
    guard(); core.analysis.Close()
    guard(); RAW_SYSTEM.LoadFile(str(seed), False)
    guard(); RAW_SYSTEM.Tools.RemoveAllVariables()
    RAW_SYSTEM.SystemData.Advanced.TurnOffThreading = True
    RAW_SYSTEM.SystemData.RayAiming.RayAiming = core.Z.SystemData.RayAimingMethod.Real
    for catalog in sorted(set(combo['catalogs'])):
        guard(); RAW_SYSTEM.SystemData.MaterialCatalogs.AddCatalog(catalog)
    NATIVE_MATERIALS = []
    for i, material in zip(SURFACES, combo['materials']):
        guard(); s = RAW_SYSTEM.LDE.GetSurfaceAt(i); s.Material = material
        if str(s.Material).upper() != material.upper(): raise RuntimeError('Material assignment failed: ' + material)
        NATIVE_MATERIALS.append(str(s.Material))
    # INDX resolves the loaded full dispersion model at every actual wavelength.
    NATIVE_N6 = [[core.sys.MFE.GetOperandValue(core.Z.Editors.MFE.MeritOperandType.INDX,
                  i, w, 0, 0, 0, 0, 0, 0) for w in range(1, 7)] for i in range(1, 13)]
    for i in SURFACES:
        if min(NATIVE_N6[i-1]) <= 1.01: raise RuntimeError('Unresolved glass: ' + str(i))
    core.indices = [row[0] for row in NATIVE_N6]
    core.base_r = np.array([RAW_SYSTEM.LDE.GetSurfaceAt(i).Radius for i in core.RIDS])
    core.base_t = np.array([RAW_SYSTEM.LDE.GetSurfaceAt(i).Thickness for i in core.TIDS])
    core.base_focus = RAW_SYSTEM.LDE.GetSurfaceAt(12).Thickness
    s = RAW_SYSTEM.LDE.GetSurfaceAt(10)
    # Sources must already satisfy A6. Never silently truncate a high-order source.
    if any(abs(s.GetCellAt(i).DoubleValue) > 0 for i in range(15, 20)):
        raise ValueError('Overnight seed must already have no A8 through A16')
    normalized = np.array([s.GetCellAt(13).DoubleValue*15.5**4, s.GetCellAt(14).DoubleValue*15.5**6])
    BASE_B = Polynomial(normalized).convert(kind=Legendre, domain=[0, 1]).coef
    for i in range(RAW_SYSTEM.LDE.NumberOfSurfaces): RAW_SYSTEM.LDE.GetSurfaceAt(i).Conic = 0.
    for i, cap in core.caps.items(): RAW_SYSTEM.LDE.GetSurfaceAt(i).MechanicalSemiDiameter = cap
    core.analysis = GuardedAnalysis(RAW_SYSTEM.Analyses.New_FftMtf())
    core.settings = core.Z.Analysis.Settings.Mtf.IAS_FftMtf(core.analysis.GetSettings())
    core.settings.MaximumFrequency = 20
    core.settings.SampleSize = getattr(core.Z.Analysis.SampleSizes, f'S_{size}x{size}')
    core.settings.Wavelength.UseAllWavelengths()
    core.apply = apply
    core.geometry = geometry
    ACTIVE_KEY = key

def apply(x):
    guard()
    coefficients = Legendre(BASE_B + x[:2]*.025, domain=[0, 1]).convert(kind=Polynomial).coef / 15.5**np.array([4, 6])
    s = RAW_SYSTEM.LDE.GetSurfaceAt(10); s.Conic = 0.; s.GetCellAt(12).DoubleValue = 0.
    for i, v in zip([13, 14], coefficients): s.GetCellAt(i).DoubleValue = float(v)
    for i in range(15, 20): s.GetCellAt(i).DoubleValue = 0.
    rr = core.base_r*(1+x[2:13]*.03); tt = core.base_t+x[13:24]*.35
    for i, v in zip(core.RIDS, rr): RAW_SYSTEM.LDE.GetSurfaceAt(i).Radius = float(v)
    for i, v in zip(core.TIDS, tt): RAW_SYSTEM.LDE.GetSurfaceAt(i).Thickness = float(v)
    RAW_SYSTEM.LDE.GetSurfaceAt(12).Thickness = float(core.base_focus)
    return coefficients, rr, tt

def geometry(coefficients):
    global ACTUAL_GAPS, STOP_AIR_GAP
    ACTUAL_GAPS = ORIGINAL_GEOMETRY(coefficients)
    radius = min(core.caps[6], core.caps[8]); r = np.linspace(0, radius, 301)
    def sag(i):
        rad = RAW_SYSTEM.LDE.GetSurfaceAt(i).Radius
        if not np.isfinite(rad): return np.zeros_like(r)
        if max(r) >= abs(rad): return np.full_like(r, np.nan)
        return r*r/(rad*(1+np.sqrt(1-(r/rad)**2)))
    values = RAW_SYSTEM.LDE.GetSurfaceAt(6).Thickness+RAW_SYSTEM.LDE.GetSurfaceAt(7).Thickness+sag(8)-sag(6)
    STOP_AIR_GAP = float(min(values)) if np.all(np.isfinite(values)) else -100.
    # Both constraints use 0.3mm. Inject their minimum solely for core's
    # pre-trace validity gate; restore each actual physical gap in the record.
    gated = ACTUAL_GAPS.copy(); gated[7] = min(gated[7], STOP_AIR_GAP)
    return gated

def evaluate(x, seed, combo, size, round_end, save=None):
    global ROUND_END
    ROUND_END = round_end; guard(); prepare(seed, combo, size)
    _, record = core.evaluate(np.r_[x, 0.], save)
    record['geometry_gaps'] = ACTUAL_GAPS
    vals = np.array(record['results_flat']); deficit = core.refs+.009-vals
    positive = .006*np.logaddexp(0, deficit/.006)
    largest = float(max(deficit)); smooth = largest+.004*np.log(np.sum(np.exp((deficit-largest)/.004)))
    fo = np.array(record['first_order']); lag = record['image_distance_mm']-fo[1]
    violation = np.maximum(GAP_LIMITS-np.array(record['geometry_gaps']), 0)
    residual = np.r_[positive**2/.065, 12*max(0, smooth),
                     (fo-FO_TARGET)*[1.5, 1., .55, .35],
                     max(0, abs(record['chief_full_field_height_mm']-193)-.3)*.05,
                     violation*8, max(0, .3-STOP_AIR_GAP)*8, max(0, abs(lag)-.25)*.2, np.asarray(x)*.0001]
    s = RAW_SYSTEM.LDE.GetSurfaceAt(10)
    actual = [s.GetCellAt(i).DoubleValue for i in range(12, 20)]
    assert actual[0] == 0 and all(v == 0 for v in actual[3:]) and s.Conic == 0
    perfn = {}; margins = core.refs-vals; offset = 0
    for fn in ['5.6', '8', '22']:
        count = np.array(core.target['data'][fn]).size
        perfn[fn] = float(max(margins[offset:offset+count])); offset += count
    record.pop('asphere_A4_to_A12', None)
    record.update(asphere_powers=[4, 6], asphere_A4_A6=actual[1:3], A2=0., A8_to_A16=actual[3:], conic=0.,
                  highest_nonzero_aspheric_power=6,
                  materials=NATIVE_MATERIALS, catalogs=combo['catalogs'], material_combo=combo,
                  refractive_indices_surfaces_1_to_12_at_all_6_wavelengths=NATIVE_N6,
                  sampling=size, max_shortfall_by_aperture=perfn,
                  all_factory_values_met=bool(np.all(vals >= core.refs)),
                  factory_values_met_count=int(np.count_nonzero(vals >= core.refs)),
                  worker_pid=os.getpid(), focus_minus_paraxial_bfl_mm=float(lag))
    record.update(stop_crossing_air_gap_S6_to_S8_mm=STOP_AIR_GAP,
                  all_surface_conics=[float(RAW_SYSTEM.LDE.GetSurfaceAt(i).Conic) for i in range(RAW_SYSTEM.LDE.NumberOfSurfaces)],
                  cdgm_cost_proxy=cost_proxy(combo),
                  objective_settings={'factory_margin': .009, 'positive_softplus_temperature': .006,
                                      'optical_residual': 'softplus(deficit)^2 / 0.065',
                                      'max_temperature': .004, 'max_normalization': 'unnormalized_logsumexp',
                                      'max_residual_weight': 12., 'selection_score': 'max_shortfall + 0.2 * deficit_rms'})
    return residual.tolist(), record

def precondition(seed, combo, size, round_end):
    global ROUND_END
    ROUND_END = round_end; guard(); prepare(seed, combo, size)
    # A reused worker may still contain its last finite-difference trial.
    # Restore the unchanged source/base prescription before numerical correction.
    apply(np.zeros(25))
    radii = [RAW_SYSTEM.LDE.GetSurfaceAt(i).Radius for i in range(1, 13)]
    thickness = [RAW_SYSTEM.LDE.GetSurfaceAt(i).Thickness for i in range(1, 12)]
    surface = RAW_SYSTEM.LDE.GetSurfaceAt(10)
    coefficients = [surface.GetCellAt(i).DoubleValue for i in [13, 14]]
    x0, metadata = solve_fo_precondition(radii, thickness, coefficients, core.indices, core.caps, guard)
    metadata.update(materials=NATIVE_MATERIALS, catalogs=combo['catalogs'],
                    actual_indices_at_all_6_wavelengths=NATIVE_N6, worker_pid=os.getpid())
    return x0, metadata

def read_plan(path, phase):
    if not path.exists(): return {'per_element': [], 'seed_combinations': []}
    document = json.loads(path.read_text(encoding='utf-8'))
    if document.get('surface_order', SURFACES) != SURFACES: raise ValueError('Unsupported glass surface order')
    result = document['phases']['mixed' if phase == 'general' else 'all_cdgm']
    result['seed_combinations'] = [q for q in result['seed_combinations']
        if 'D263' not in ' '.join(q['materials']) and (phase != 'cdgm' or all(c.upper() == 'CDGM' for c in q['catalogs']))]
    return result

def source_combo(seed):
    # Native zmx materials are ASCII rows even when the file itself uses UTF16.
    raw = Path(seed).read_bytes(); text = raw.decode('utf-16') if raw[:2] in [b'\xff\xfe', b'\xfe\xff'] else raw.decode('utf-8')
    surfaces = {}; current = None
    for line in text.splitlines():
        fields = line.strip().split()
        if fields and fields[0] == 'SURF': current = int(fields[1])
        if fields and fields[0] == 'GLAS': surfaces[current] = fields[1]
    return {'id': 'source_materials', 'materials': [surfaces[i] for i in SURFACES], 'catalogs': ['SCHOTT']*6}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--seed', required=True); p.add_argument('--phase', choices=['general', 'cdgm'], required=True)
    p.add_argument('--deadline-utc', required=True); p.add_argument('--workers', type=int, default=8)
    p.add_argument('--catalog-plan', default=str(BASE/'catalog_plan.json'))
    p.add_argument('--target', default=str(core.ROOT/'revision3'/'target_optimization.json'))
    p.add_argument('--round-seconds', type=float, default=720); p.add_argument('--max-rounds', type=int, default=10000)
    p.add_argument('--max-jacobians', type=int, default=12); p.add_argument('--iterations', type=int, default=35)
    p.add_argument('--guard-seconds', type=float, default=25); p.add_argument('--sampling', type=int, choices=[128, 256], default=256)
    p.add_argument('--resume', action='store_true'); a = p.parse_args()
    if not 1 <= a.workers <= 8: p.error('workers must be 1 through 8')
    deadline = dt.datetime.fromisoformat(a.deadline_utc.replace('Z', '+00:00'))
    if deadline.tzinfo is None: p.error('deadline requires explicit UTC offset')
    end = deadline.timestamp(); out = BASE/a.phase; out.mkdir(parents=True, exist_ok=True)
    seed = str(Path(a.seed).resolve()); combo = source_combo(seed); best = None; serial = 0
    existing = list((out/'best').glob('candidate_*.zmx'))
    if existing: serial = max(int(q.stem.split('_')[-1]) for q in existing)
    if a.resume and (out/'best.json').exists():
        best = json.loads((out/'best.json').read_text()); seed = best['source_path']; combo = best['material_combo']; serial = max(serial, int(best['serial']))
    random_generator = random.Random(15020260915); tried = set(); evaluations = 0; start = time.time()
    combo_bests = {}
    for pointer in (out/'combo_bests').glob('*/best.json'):
        value = json.loads(pointer.read_text(encoding='utf-8')); combo_bests[combo_key(value['material_combo'])] = value
    atomic_json(out/'status.json', {'pid': os.getpid(), 'phase': a.phase, 'state': 'starting', 'workers': a.workers,
                                  'deadline_utc': deadline.isoformat(), 'seed': seed})
    pool = None; status = 'deadline'
    def next_snapshot():
        nonlocal serial
        serial += 1; snapshot = out/'best'/f'candidate_{serial:05d}.zmx'
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        while snapshot.exists() or snapshot.with_suffix('.json').exists():
            serial += 1; snapshot = out/'best'/f'candidate_{serial:05d}.zmx'
        return snapshot
    try:
        if time.time() >= end-a.guard_seconds: raise DeadlineReached('Already inside closing margin')
        pool = ProcessPoolExecutor(max_workers=a.workers, mp_context=mp.get_context('spawn'),
            initializer=initialize, initargs=(seed, a.target, a.phase, end, a.guard_seconds))
        # Resume comparison is rebuilt solely from common FFT256 records.
        # A formerly winning FFT128 score must never block its fresh FFT256 result.
        previous = list(combo_bests.values()) + ([best] if best else [])
        normalized = {}; seen_sources = set()
        for old in previous:
            source = old['source_path']; source_hash = digest(source)
            if source_hash in seen_sources: continue
            seen_sources.add(source_hash)
            if int(old.get('sampling', 0)) != 256:
                snapshot = next_snapshot()
                _, fresh = pool.submit(evaluate, np.zeros(24), source, old['material_combo'], 256,
                                       end-a.guard_seconds, str(snapshot)).result()
                evaluations += 1
                # Only metadata is added: preserve every native high-sampling value.
                fresh.update(score=fresh['max_shortfall']+.2*fresh['deficit_rms'], feasible=record_feasible(fresh),
                             serial=serial, source_path=str(snapshot.resolve()), source_sha256=digest(snapshot),
                             checkpoint_path=str(snapshot.with_suffix('.json').resolve()), seed=source,
                             source_seed_sha256=source_hash, phase=a.phase,
                             catalog_plan_path=str(Path(a.catalog_plan).resolve()),
                             catalog_plan_sha256=digest(a.catalog_plan) if Path(a.catalog_plan).exists() else None,
                             normalization={'sampling': 256, 'previous_sampling': old.get('sampling'),
                                            'previous_source_path': source, 'previous_source_sha256': source_hash,
                                            'previous_serial': old.get('serial')})
                atomic_json(snapshot.with_suffix('.json'), fresh)
                print('NORMALIZE256', serial, 'max', fresh['max_shortfall'], 'feasible', fresh['feasible'], flush=True)
            else:
                fresh = dict(old, score=old['max_shortfall']+.2*old['deficit_rms'], feasible=record_feasible(old))
            key = combo_key(fresh['material_combo'])
            if not fresh['feasible']:
                atomic_json(out/'combo_bests'/key/'best.json', fresh)
            if fresh['feasible'] and (key not in normalized or fresh['score'] < normalized[key]['score']):
                normalized[key] = fresh
        combo_bests = normalized
        for key, fresh in combo_bests.items():
            atomic_json(out/'combo_bests'/key/'best.json', fresh)
            history = out/'combo_bests'/key/f"candidate_{fresh['serial']:05d}.json"
            if not history.exists(): atomic_json(history, fresh)
        if previous:
            best = min(combo_bests.values(), key=lambda q: q['score']) if combo_bests else None
            if best: atomic_json(out/'best.json', best)
            write_pareto(out, combo_bests)
        # A resumed pool should explore remaining material seeds rather than
        # repeat every combination that already has a native feasible snapshot.
        tried.update(tuple(value['materials']) for value in combo_bests.values())
        for round_number in range(a.max_rounds):
            if time.time() >= end-a.guard_seconds: raise DeadlineReached('Phase closing margin reached')
            plan = read_plan(Path(a.catalog_plan), a.phase)
            if best: seed = best['source_path']; combo = best['material_combo']
            choices = [c for c in plan['seed_combinations'] if tuple(c['materials']) not in tried]
            material_round = a.phase == 'cdgm' and best is None or round_number % 2 == 1
            if material_round and choices: combo = choices[0]
            elif material_round and plan['per_element']:
                combo = dict(combo, materials=list(combo['materials']), catalogs=list(combo['catalogs']), id=f'mutation_{round_number}')
                element = random_generator.choice(plan['per_element']); idx = SURFACES.index(element['surface'])
                candidates = [c for c in element['candidates'] if 'D263' not in c['material'] and
                              (a.phase != 'cdgm' or c['catalog'].upper() == 'CDGM')]
                if candidates:
                    glass = random_generator.choice(candidates); combo['materials'][idx] = glass['material']; combo['catalogs'][idx] = glass['catalog']
            if a.phase == 'cdgm' and not all(c.upper() == 'CDGM' for c in combo['catalogs']):
                raise RuntimeError('No all-CDGM seed combination available; refusing non-CDGM fallback')
            tried.add(tuple(combo['materials']))
            round_end = min(time.time()+a.round_seconds, end-a.guard_seconds)
            size = 256 if best and round_number % 4 == 0 else a.sampling
            jacobians = 0; local_count = 0
            precondition_metadata = {'enabled': False}
            def fun(x):
                nonlocal best, serial, evaluations, local_count
                residual, record = pool.submit(evaluate, x, seed, combo, size, round_end).result()
                evaluations += 1; local_count += 1
                fo = np.array(record['first_order']); feasible = record_feasible(record)
                score = record['max_shortfall']+.2*record['deficit_rms']
                record.update(score=score, feasible=bool(feasible), round=round_number, eval=evaluations,
                              seconds=time.time()-start, seed=seed, source_seed_sha256=digest(seed), phase=a.phase,
                              catalog_plan_path=str(Path(a.catalog_plan).resolve()),
                              catalog_plan_sha256=digest(a.catalog_plan) if Path(a.catalog_plan).exists() else None,
                              material_fo_precondition=precondition_metadata)
                atomic_json(out/'current.json', record)
                key = combo_key(combo)
                global_improved = feasible and (best is None or score < best['score'])
                combo_improved = feasible and (key not in combo_bests or score < combo_bests[key]['score'])
                if global_improved or combo_improved:
                    snapshot = next_snapshot()
                    _, saved = pool.submit(evaluate, x, seed, combo, size, round_end, str(snapshot)).result()
                    saved.update(score=saved['max_shortfall']+.2*saved['deficit_rms'], feasible=record_feasible(saved),
                                 serial=serial, source_path=str(snapshot.resolve()), source_sha256=digest(snapshot),
                                 checkpoint_path=str(snapshot.with_suffix('.json').resolve()), seed=seed,
                                 source_seed_sha256=digest(seed), phase=a.phase, round=round_number, eval=evaluations,
                                 seconds=time.time()-start, catalog_plan_path=str(Path(a.catalog_plan).resolve()),
                                 catalog_plan_sha256=digest(a.catalog_plan) if Path(a.catalog_plan).exists() else None,
                                 material_fo_precondition=precondition_metadata)
                    global_improved = saved['feasible'] and (best is None or saved['score'] < best['score'])
                    combo_improved = saved['feasible'] and (key not in combo_bests or saved['score'] < combo_bests[key]['score'])
                    atomic_json(snapshot.with_suffix('.json'), saved)
                    if combo_improved:
                        combo_bests[key] = saved
                        atomic_json(out/'combo_bests'/key/f'candidate_{serial:05d}.json', saved)
                        atomic_json(out/'combo_bests'/key/'best.json', saved)
                        write_pareto(out, combo_bests)
                    if global_improved:
                        atomic_json(out/'best.json', saved); best = saved
                    print('GLOBAL_BEST' if global_improved else 'COMBO_BEST', a.phase, serial, 'max', round(record['max_shortfall'], 7), 'rms', round(record['deficit_rms'], 7), combo['materials'], flush=True)
                atomic_json(out/'status.json', {'pid': os.getpid(), 'phase': a.phase, 'state': 'searching', 'round': round_number,
                    'round_evaluations': local_count, 'jacobians': jacobians, 'total_evaluations': evaluations,
                    'workers': a.workers, 'deadline_utc': deadline.isoformat(), 'best_source': best['source_path'] if best else None,
                    'best_max_shortfall': best['max_shortfall'] if best else None, 'current_materials': combo['materials'],
                    'updated_utc': dt.datetime.now(dt.timezone.utc).isoformat()})
                print('EVAL', round_number, local_count, 'max', round(record['max_shortfall'], 6), 'fo', np.round(fo, 3), flush=True)
                return np.array(residual)
            def jac(x):
                nonlocal jacobians
                if jacobians >= a.max_jacobians: raise RoundExpired('Jacobian budget reached')
                jacobians += 1
                steps = np.r_[[.0015]*2, [.01]*22]
                # Only one batch is outstanding; every queued job checks deadline before native calls.
                jobs = []
                for i, h in enumerate(steps):
                    plus = x.copy(); minus = x.copy(); plus[i] += h; minus[i] -= h
                    jobs.append((pool.submit(evaluate, plus, seed, combo, size, round_end),
                                 pool.submit(evaluate, minus, seed, combo, size, round_end)))
                return np.array([(np.array(p.result()[0])-np.array(m.result()[0]))/(2*h) for (p, m), h in zip(jobs, steps)]).T
            low = np.r_[[-12.]*2, [-3.]*11, [-2.]*11]; low[19] = -2.5
            x0 = np.zeros(24)
            if best and round_number > 1 and not material_round:
                # Small independent restarts explore the local shape basin while
                # the immutable feasible best remains available if a trial fails.
                x0 = np.array([random_generator.uniform(-.02, .02) for _ in range(24)])
            try:
                if material_round:
                    start_vector, precondition_metadata = pool.submit(precondition, seed, combo, size, round_end).result()
                    x0 = np.array(start_vector)
                    atomic_json(out/'rounds'/f'round_{round_number:04d}_precondition.json', precondition_metadata)
                    print('FO_PRECONDITION', round_number, 'before', precondition_metadata['before_first_order'],
                          'after', precondition_metadata['after_first_order'], 'feasible', precondition_metadata['feasible'], flush=True)
                result = least_squares(fun, x0, jac=jac, bounds=(low, -low), x_scale=1.,
                    max_nfev=a.iterations, ftol=2e-6, xtol=1e-7, gtol=1e-7)
                message = str(result.message)
            except RoundExpired as exc: message = str(exc)
            except RuntimeError as exc:
                if isinstance(exc, DeadlineReached): raise
                message = 'Candidate failed: ' + str(exc)
            atomic_json(out/'rounds'/f'round_{round_number:04d}.json', {'round': round_number, 'materials': combo,
                        'seed': seed, 'sampling': size, 'jacobians': jacobians, 'evals': local_count, 'status': message,
                        'material_fo_precondition': precondition_metadata})
            print('ROUND_END', round_number, message, flush=True)
        status = 'max_rounds'
    except DeadlineReached as exc: status = str(exc)
    finally:
        if pool: pool.shutdown(wait=True, cancel_futures=True)
        atomic_json(out/'status.json', {'pid': os.getpid(), 'phase': a.phase, 'state': 'closed', 'status': status,
                   'native_apps_owned': 0, 'workers': a.workers, 'total_evaluations': evaluations,
                   'best_source': best['source_path'] if best else None, 'closed_utc': dt.datetime.now(dt.timezone.utc).isoformat()})
        print('CLOSED', a.phase, status, 'best', best['source_path'] if best else None, flush=True)

if __name__ == '__main__': main()
