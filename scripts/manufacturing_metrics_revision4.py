"""Compute geometric manufacturing descriptors from validated R4 data, no ZOS.

These are nominal design geometry, not achievable precision, tolerance,
process qualification, cost, lead time, or production-yield guarantees.
The reference sphere is the S10 prescribed vertex-radius sphere, NOT a fitted
best-fit sphere. Its departure must not be confused with an asphere form error.
"""
from pathlib import Path
import argparse
import json
import hashlib
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

P = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--input', type=Path, default=P/'revision4/validated.json')
parser.add_argument('--r2', type=Path, default=P/'revision2/validated.json')
parser.add_argument('--samples', type=int, default=20001)
parser.add_argument('--rear-extended-radius', type=float, default=15.8)
args = parser.parse_args()
if args.samples < 2001:
    raise ValueError('Use at least 2001 radial samples.')
v = json.loads(args.input.read_text(encoding='utf-8'))
source_sha256 = v.get('source_sha256')
if not isinstance(source_sha256, str) or len(source_sha256) != 64 or any(c not in '0123456789abcdefABCDEF' for c in source_sha256):
    raise ValueError('Manufacturing metrics require validated.source_sha256 for the frozen final source.')
source_sha256 = source_sha256.lower()
if len(v['surfaces']) != 12 or any('conic' not in s or float(s['conic']) != 0 for s in v['surfaces']):
    raise ValueError('R4 manufacturing metrics require explicit zero conic on all twelve surfaces.')
if float(v.get('asphere_conic', 0)) != 0:
    raise ValueError('R4 top-level asphere_conic must also be zero.')
surface_signature = [{'surface': int(s['surface']), 'radius_mm': float(s['radius_mm']),
                      'thickness_mm': float(s['thickness_mm']), 'glass': str(s['glass']),
                      'clear_radius_mm': float(s['clear_radius_mm']),
                      'mechanical_radius_mm': float(s['mechanical_radius_mm']),
                      'stop': bool(s['stop']), 'conic': float(s['conic'])}
                     for s in sorted(v['surfaces'], key=lambda row: int(row['surface']))]
if [s['surface'] for s in surface_signature] != list(range(1, 13)):
    raise ValueError('R4 surface signature must contain each surface 1 through 12 exactly once.')
surface_signature_sha256 = hashlib.sha256(json.dumps(surface_signature, sort_keys=True, separators=(',', ':'), allow_nan=True).encode('utf-8')).hexdigest()
old = json.loads(args.r2.read_text(encoding='utf-8'))
R = args.input.resolve().parent
sur = {int(s['surface']): s for s in v['surfaces']}
prev = {int(s['surface']): s for s in old['surfaces']}
coeff = np.asarray(v.get('asphere_A4_to_A6', []), dtype=float)
if coeff.shape != (2,):
    raise ValueError('R4 requires exactly two coefficients, A4 and A6.')
for key in ['asphere_A4_to_A12', 'asphere_A4_to_A16']:
    if key in v and np.any(np.asarray(v[key], dtype=float)[2:] != 0):
        raise ValueError(f'R4 forbids nonzero A8 and higher: {key}')
if 'asphere_powers' in v and list(v['asphere_powers']) != [4, 6]:
    raise ValueError('R4 asphere_powers must be [4, 6].')
powers = np.asarray([4, 6])
conic = float(v.get('asphere_conic', sur[10].get('conic', 0.0)))

def base_sag_and_slope(radius, r, k=0.0):
    r = np.asarray(r, dtype=float)
    if not math.isfinite(radius):
        return np.zeros_like(r), np.zeros_like(r)
    c = 1.0/radius
    root2 = 1.0-(1.0+k)*c*c*r*r
    if np.any(root2 <= 0):
        raise ValueError('Requested radius exceeds real conic domain.')
    root = np.sqrt(root2)
    sag = c*r*r/(1.0+root)
    # Exact derivative for this vertex-radius/conic sag convention.
    slope = c*r/root
    return sag, slope

def sag_and_slope(i, r):
    r = np.asarray(r, dtype=float)
    base, slope = base_sag_and_slope(float(sur[i]['radius_mm']), r, conic if i == 10 else 0.0)
    if i == 10:
        base += sum(a*r**int(p) for a,p in zip(coeff,powers))
        slope += sum(int(p)*a*r**(int(p)-1) for a,p in zip(coeff,powers))
    return base, slope

def grid(radius):
    return np.linspace(0.0, float(radius), args.samples)

def extreme(values, rr, mode='abs'):
    ix = int(np.argmax(abs(values)) if mode == 'abs' else np.argmin(values))
    return {'value': float(values[ix]), 'radius_mm': float(rr[ix])}

rr = grid(sur[10]['clear_radius_mm'])
actual, actual_slope = sag_and_slope(10, rr)
sphere, sphere_slope = base_sag_and_slope(float(sur[10]['radius_mm']), rr)
departure = actual-sphere
slope_departure = actual_slope-sphere_slope
angles = np.degrees(np.arctan(actual_slope))
sphere_angles = np.degrees(np.arctan(sphere_slope))
angle_departure = angles-sphere_angles
asphere = {
    'surface': 10,
    'prescribed_vertex_radius_mm': float(sur[10]['radius_mm']),
    'conic': conic,
    'clear_radius_mm': float(rr[-1]),
    'coefficient_powers': list(map(int,powers)),
    'coefficients': list(map(float,coeff)),
    'coefficient_units': [f'mm^{1-int(p)}' for p in powers],
    'reference': 'Prescribed vertex-radius sphere, not best-fit sphere; departure is designed shape, not form-error tolerance.',
    'departure_min_um': float(np.min(departure)*1000),
    'departure_max_um': float(np.max(departure)*1000),
    'departure_pv_um': float(np.ptp(departure)*1000),
    'maximum_absolute_departure_um': {'value': abs(extreme(departure,rr)['value'])*1000, 'radius_mm': extreme(departure,rr)['radius_mm']},
    'maximum_absolute_surface_slope_mm_per_mm': {'value': abs(extreme(actual_slope,rr)['value']), 'radius_mm': extreme(actual_slope,rr)['radius_mm']},
    'maximum_absolute_slope_departure_mm_per_mm': {'value': abs(extreme(slope_departure,rr)['value']), 'radius_mm': extreme(slope_departure,rr)['radius_mm']},
    'maximum_absolute_surface_angle_deg': {'value': abs(extreme(angles,rr)['value']), 'radius_mm': extreme(angles,rr)['radius_mm']},
    'maximum_absolute_angle_departure_deg': {'value': abs(extreme(angle_departure,rr)['value']), 'radius_mm': extreme(angle_departure,rr)['radius_mm']},
    'edge': {'radius_mm': float(rr[-1]), 'asphere_sag_mm': float(actual[-1]),
             'reference_sphere_sag_mm': float(sphere[-1]), 'departure_um': float(departure[-1]*1000),
             'asphere_slope_mm_per_mm': float(actual_slope[-1]), 'sphere_slope_mm_per_mm': float(sphere_slope[-1]),
             'slope_departure_mm_per_mm': float(slope_departure[-1]),
             'surface_angle_deg': float(angles[-1]), 'sphere_angle_deg': float(sphere_angles[-1]),
             'angle_departure_deg': float(angle_departure[-1])}
}
elements = []
for element_id, front in enumerate([1,3,5,8,9,11], 1):
    back = front+1
    radius = min(sur[front]['clear_radius_mm'], sur[back]['clear_radius_mm'])
    r = grid(radius)
    front_sag, _ = sag_and_slope(front,r)
    back_sag, _ = sag_and_slope(back,r)
    thick = float(sur[front]['thickness_mm'])+back_sag-front_sag
    minimum = extreme(thick,r,mode='min')
    elements.append({'element': element_id, 'glass': sur[front]['glass'],
                     'front_surface': front, 'back_surface': back,
                     'common_effective_radius_mm': float(radius), 'common_effective_diameter_mm': float(2*radius),
                     'center_thickness_mm': float(sur[front]['thickness_mm']),
                     'minimum_thickness_mm': minimum['value'], 'minimum_at_radius_mm': minimum['radius_mm'],
                     'edge_thickness_mm': float(thick[-1]),
                     'center_thickness_change_from_R2_mm': float(sur[front]['thickness_mm']-prev[front]['thickness_mm']),
                     'domain': 'Common front/back optical clear aperture only; excludes undefined bevel and mechanical edge.'})
gaps = []
for name, front, back in [('L1 to L2',2,3),('L2 to L3',4,5),('L3 to cemented group (stop between)',6,8),('cemented group to last element',10,11)]:
    radius = min(sur[front]['clear_radius_mm'],sur[back]['clear_radius_mm'])
    r = grid(radius)
    axial = sum(float(sur[i]['thickness_mm']) for i in range(front,back))
    fs, _ = sag_and_slope(front,r)
    bs, _ = sag_and_slope(back,r)
    value = axial+bs-fs
    minimum = extreme(value,r,mode='min')
    gaps.append({'name': name, 'front_surface': front, 'back_surface': back,
                 'center_gap_mm': axial, 'checked_radius_mm': float(radius),
                 'minimum_gap_mm': minimum['value'], 'minimum_at_radius_mm': minimum['radius_mm'],
                 'domain': 'Common effective optical aperture'})
rear_r = grid(args.rear_extended_radius)
rear_front, _ = sag_and_slope(10,rear_r)
rear_back, _ = sag_and_slope(11,rear_r)
rear_gap = float(sur[10]['thickness_mm'])+rear_back-rear_front
rear_min = extreme(rear_gap,rear_r,mode='min')
conservative = {'front_surface':10,'back_surface':11,
                'checked_radius_mm':float(args.rear_extended_radius),
                'minimum_gap_mm':rear_min['value'],'minimum_at_radius_mm':rear_min['radius_mm'],
                'positive_nominal_gap':rear_min['value']>0,
                'domain': 'Conservative continuation of S10 and S11 optical shapes to radius 15.8 mm by default, including reading margin beyond specified clear apertures. Mechanical bevel is not defined. This is a geometric test, not a tolerance-guaranteed assembly gap.'}
changes = []
for i,s in sorted(sur.items()):
    p = prev[i]
    changes.append({'surface':i,'glass':s['glass'],'stop':bool(s.get('stop',False)),
                    'R2_center_distance_mm':float(p['thickness_mm']), 'R4_center_distance_mm':float(s['thickness_mm']),
                    'center_distance_change_mm':float(s['thickness_mm']-p['thickness_mm']),
                    'radius_change_mm':float(s['radius_mm']-p['radius_mm']) if math.isfinite(s['radius_mm']) and math.isfinite(p['radius_mm']) else None,
                    'R2_clear_radius_mm':float(p['clear_radius_mm']),'R4_clear_radius_mm':float(s['clear_radius_mm']),
                    'clear_radius_change_mm':float(s['clear_radius_mm']-p['clear_radius_mm']),
                    'note':'Automatic stop size depends on aperture state; not a fixed lens-edge production dimension.' if s.get('stop') else ('Image distance, not glass center thickness.' if i==12 else '')})
metrics = {'input':str(args.input.resolve()),'comparison_R2':str(args.r2.resolve()),
           'source_sha256':source_sha256, 'surface_signature':surface_signature,
           'surface_signature_sha256':surface_signature_sha256,
           'method':'Analytic sag and first derivative, 20001 uniformly spaced radial samples by default; extrema include axis and clear edge.',
           'radial_sample_count':args.samples, 'asphere':asphere,'glass_elements':elements,
           'air_gaps_common_aperture':gaps,'rear_gap_conservative_extension':conservative,
           'surface_changes_from_R2':changes,
           'warnings': ['Nominal geometry only. No process precision, manufacturing cost, tolerance, yield or supplier qualification is inferred.',
                        'Element thickness excludes bevels and other mechanical features not defined in validated.json.',
                        'All twelve conics must be explicitly stored as zero. R4 is restricted to A4 and A6; nonzero A8 and higher are rejected. Low polynomial order does not prove historical or present manufacturing capability.',
                        'Asphere departure is measured against the prescribed vertex-radius sphere. It is not residual error against a best-fit sphere or an allowed form error.',
                        'Finite radial sampling locates extrema approximately; analytic first derivatives are exact for the stored conic-polynomial representation.']}
if len(elements)!=6:
    raise AssertionError('Expected six glass elements.')
fig,axes = plt.subplots(2,2,figsize=(11,7))
axes[0,0].plot(rr,actual,label='Asphere',color='#1f77b4')
axes[0,0].plot(rr,sphere,label='Vertex-radius sphere',color='#d95f02',ls='--')
axes[0,0].set_ylabel('Sag (mm)');axes[0,0].set_title('S10 sag relative to vertex')
axes[0,1].plot(rr,departure*1000,color='#7570b3')
axes[0,1].set_ylabel('Designed departure (um)');axes[0,1].set_title('Asphere minus prescribed sphere')
axes[1,0].plot(rr,actual_slope,label='Asphere',color='#1f77b4')
axes[1,0].plot(rr,sphere_slope,label='Vertex-radius sphere',color='#d95f02',ls='--')
axes[1,0].set_ylabel('Signed slope dz/dr (mm/mm)');axes[1,0].set_title('Analytic surface slopes')
axes[1,1].plot(rr,slope_departure,color='#7570b3')
axes[1,1].set_ylabel('Slope departure (mm/mm)');axes[1,1].set_title('Asphere slope minus sphere slope')
for ax in axes.flat:
    ax.set_xlabel('Radial coordinate (mm)');ax.grid(alpha=.2)
fig.suptitle('R4 nominal S10 geometry: designed shape, not a manufacturing tolerance')
handles, labels = axes[0,0].get_legend_handles_labels()
fig.legend(handles, labels, ncol=2, fontsize=10, loc='lower center', bbox_to_anchor=(.5, .005), frameon=False)
fig.tight_layout(rect=(0, .07, 1, .95));fig.savefig(R/'asphere_profile.png',dpi=180);plt.close(fig)
metrics['asphere_profile_sha256'] = hashlib.sha256((R/'asphere_profile.png').read_bytes()).hexdigest()
(R/'manufacturing_geometry_metrics.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False),encoding='utf-8')
print('Manufacturing geometry metrics generated; no ZOS instance used.')

