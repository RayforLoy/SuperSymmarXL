"""Attach independent window-convergence findings to partial native audit.

No ZOS. Run after the independent window files exist. Never marks
convergence proved solely from one pair of finite image windows.
"""
from pathlib import Path
import json
import numpy as np
P=Path(__file__).resolve().parents[1];R=P/'revision3'
path=R/'huygens_validation.json'
report=json.loads(path.read_text(encoding='utf-8'))
checks={}
for name in ['huygens_axis_window512','huygens_axis_wide_window','huygens_window1024','huygens_f22_axis_fixed','huygens_pupil256_fixed_window']:
    file=R/(name+'.json')
    if file.exists():
        d=json.loads(file.read_text(encoding='utf-8'))
        checks[name]={'file':str(file),'model':d['model'],'settings':d['settings'],
                      'rows':d.get('rows',[]),'failures':d.get('failures',[]),'status':d.get('status'),
                      'PSF_window':(d.get('results') or [{}])[0].get('samples',{}).get('128',{}).get('HuygensPSF_window')}
summary={'checks':checks,'image_window_convergence_proven':False,
         'warning':'Automatic ImageDelta=0 with image256 is a provisional preliminary check. Changing pupil sampling also affects native automatic image spacing. Wider fixed-step windows and pupil convergence are required before treating Huygens values as accepted MTF.'}
def axis_values(name,pupil=128):
    c=checks[name]
    rows=[r for r in c['rows'] if float(r['height'])==0 and r['aperture']=='5.6' and r['pupil_sampling']==pupil]
    return np.array([r[x] for r in sorted(rows,key=lambda r:r['frequency_lp_mm']) for x in ['Huygens_T','Huygens_S']])
if all(n in checks and len(checks[n]['rows'])>=3 for n in ['huygens_axis_window512','huygens_axis_wide_window']):
    a=axis_values('huygens_axis_window512');b=axis_values('huygens_axis_wide_window')
    summary['fixed_1um_axis_image512_to1024_max_absolute_change']=float(np.max(abs(b-a)))
if all(n in checks and len(checks[n]['rows'])>=3 for n in ['huygens_axis_window512','huygens_pupil256_fixed_window']):
    a=axis_values('huygens_axis_window512');b=axis_values('huygens_pupil256_fixed_window',256)
    if len(a)==len(b)==6:
        summary['fixed_1um_image512_axis_pupil128_to256_max_absolute_change']=float(np.max(abs(b-a)))
        summary['pupil_sampling_warning']='The same fixed image window gives a 128-to-256 pupil MTF change. The larger Huygens128 values cannot be treated as proven optical improvement; full-field pupil convergence must be audited.'
full_path=R/'huygens_full_fixed_window.json'
if full_path.exists() and 'huygens_pupil256_fixed_window' in checks:
    full=json.loads(full_path.read_text(encoding='utf-8'))
    points256=checks['huygens_pupil256_fixed_window']['rows']
    candidates=[c for c in full.get('cases',[]) if c.get('aperture')=='5.6' and c.get('height')==0.6 and c.get('image_distance_offset_mm',0)==0]
    points256=[r for r in points256 if r['aperture']=='5.6' and r['height']==.6 and r['pupil_sampling']==256]
    if candidates and len(points256)==3:
        a=np.asarray(candidates[0]['values_5T_5S_10T_10S_20T_20S'])
        b=np.array([r[x] for r in sorted(points256,key=lambda r:r['frequency_lp_mm']) for x in ['Huygens_T','Huygens_S']])
        summary['fixed_1um_image512_f5p6_h0p6_pupil128_to256']={'reference_full128_file':str(full_path),'Huygens128':a.tolist(),'Huygens256':b.tolist(),'max_absolute_change':float(np.max(abs(b-a))),'warning':'Sampling sensitivity remains material. Do not interpret the full128 field curves as converged optical performance.'}
report['fixed_window_checks']=summary
report['status']='Partial preliminary automatic-window audit; fixed-window convergence checks attached. No conclusion of manufacturer superiority is drawn from unconverged Huygens data.'
warning='Huygens preliminary automatic image256 values may be biased by finite PSF window or pupil integration; see fixed_window_checks.'
if warning not in report['warnings']:report['warnings'].append(warning)
path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
print('Attached window checks, preserving original preliminary rows/settings.')
