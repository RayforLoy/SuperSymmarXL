"""Frozen full-dispersion substitution shortlist; no native optical application."""
from pathlib import Path
import json, hashlib, shutil, math, re
import numpy as np

P=Path(__file__).resolve().parent
REF=P/'reference';REF.mkdir(parents=True,exist_ok=True)
CAT=Path(r'C:\Users\liuru\Documents\Zemax\Glasscat')
W=np.array([.546,.644,.588,.480,.436,.405])
WEIGHTS=np.array([24.6,18.6,22.1,12.4,15.2,7.1])/100
ORIGINAL=['KF9','N-LAK33B','N-LAK33B','N-SK5','F2','K10']
SURFACES=[1,3,5,8,9,11]
sources=[
 {'title':'CDGM manufacturer product/catalog portal','url':'https://www.cdgmgd.com/','scope':'Manufacturer confirms optical glass product classes and downloadable Zemax data; not a per-type stock or delivered-price quote.'},
 {'title':'SCHOTT optical glass downloads','url':'https://www.schott.com/en-us/products/optical-glass-p1000267/downloads','scope':'Manufacturer publishes standard and inquiry glass lists; local 2022 AGF status is not verified 2026 stock.'},
 {'title':'Ansys AGF format specification','url':'https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v251/en/OpticStudio_User_Guide/OpticStudio_Help/topics/The_AGF_BGF_File_Formats.html','scope':'OD relative cost, NM status, and melt frequency interpretation; no common cross-vendor cost normalization is established.'}
]

def metadata_number(value):
 try:return float(value)
 except ValueError:return -1.

def load(catalog):
 path=CAT/(catalog+'.AGF');raw=path.read_bytes();snapshot=REF/(catalog+'_20260915_snapshot.AGF');shutil.copy2(path,snapshot)
 text=raw.decode('utf-16' if raw[:2] in [b'\xff\xfe',b'\xfe\xff'] else 'utf-8-sig',errors='replace')
 items=[];cur=None
 for line in text.splitlines():
  s=line.split()
  if not s:continue
  if s[0]=='NM':
   cur={'catalog':catalog,'material':s[1],'formula':int(float(s[2])),'nd_catalog':float(s[4]),'vd_catalog':float(s[5]),'exclude_substitution':int(float(s[6])),'status_code':int(float(s[7])) if len(s)>7 and s[7]!='-' else None,'melt_frequency_code':int(float(s[8])) if len(s)>8 and s[8]!='-' else None,'NM_raw':line};items.append(cur)
  elif cur is not None and s[0] in ['CD','LD','OD','ED','TD','MD']:
   cur[s[0]+'_raw']=line
   cur[s[0]]=[float(x) for x in s[1:]] if s[0] in ['CD','LD'] else [metadata_number(x) for x in s[1:]]
  elif cur is not None and s[0]=='GC':cur['comment']=' '.join(s[1:])
  elif cur is not None and s[0]=='IT':cur.setdefault('IT',[]).append(list(map(float,s[1:])))
 return items,{'catalog':catalog,'source':str(path),'snapshot':str(snapshot.relative_to(P)),'sha256':hashlib.sha256(raw).hexdigest(),'header':text.splitlines()[0]}

def index(g,w):
 c=g['CD'];q=np.asarray(w)**2
 if g['formula']==2:return np.sqrt(1+sum(c[i]*q/(q-c[i+1]) for i in [0,2,4]))
 if g['formula']==1:return np.sqrt(c[0]+c[1]*q+sum(c[i]*q**(-(i-1)) for i in range(2,6)))
 raise ValueError('Formula not implemented: '+str(g['formula']))

glass=[];snapshots=[];excluded=[]
for catalog in ['SCHOTT','CDGM']:
 data,snap=load(catalog);snapshots.append(snap)
 for g in data:
  try:
   if g['formula'] not in [1,2]:raise ValueError('Only exact AGF Schott/Sellmeier1 formulas implemented')
   if 'LD' not in g or min(W)<g['LD'][0] or max(W)>g['LD'][1]:raise ValueError('Six wavelengths outside LD validity')
   n=index(g,W)
   if not np.all(np.isfinite(n)) or min(n)<=1:raise ValueError('Invalid dispersion')
   std=index(g,np.array([.5875618,.4861327,.6562725,.4358343,.4046561,.546074,.479991,.643847]))
   nd,nf,nc,ng,nh,ne,nfp,ncp=std
   g['n_6_wavelengths']=n.tolist();g['n_at_standard_lines']={key:float(value) for key,value in zip(['d','F','C','g','h','e',"F_prime","C_prime"],std)}
   g['vd_computed']=float((nd-1)/(nf-nc));g['ve_computed']=float((ne-1)/(nfp-ncp))
   g['relative_partial_dispersion']={'P_gF':float((ng-nf)/(nf-nc)),'P_hg':float((nh-ng)/(nf-nc)),'P_dC':float((nd-nc)/(nf-nc)),'P_gFprime':float((ng-nfp)/(nfp-ncp))}
   g['nd_formula_minus_catalog']=float(nd-g['nd_catalog']);g['vd_formula_minus_catalog']=float(g['vd_computed']-g['vd_catalog'])
   if abs(g['nd_formula_minus_catalog'])>5e-4 or abs(g['vd_formula_minus_catalog'])>.3:raise ValueError('Catalog nd/Vd cross-check discrepancy')
   g['catalog_relative_cost']=g.get('OD',[-1])[0];g['price_category']='unknown' if g['catalog_relative_cost']<0 else 'local_catalog_relative_cost_only'
   g['actual_stock']='not_verified';g['delivered_price']='not_quoted';g['historical_glass_identity']='not_verified'
   glass.append(g)
  except Exception as exc:excluded.append({'catalog':catalog,'material':g['material'],'reason':str(exc)})

bykey={g['catalog']+':'+g['material']:g for g in glass}
original=[bykey['SCHOTT:'+name] for name in ORIGINAL]
manifest={};phases={}

def candidate(g,old,rank):
 n=np.array(g['n_6_wavelengths']);on=np.array(old['n_6_wavelengths']);delta=n-on
 residual=delta-np.dot(WEIGHTS,delta)
 dp={k:g['relative_partial_dispersion'][k]-old['relative_partial_dispersion'][k] for k in old['relative_partial_dispersion']}
 score=math.sqrt(np.dot(WEIGHTS,delta**2))/.01+math.sqrt(np.dot(WEIGHTS,residual**2))/.0005+abs(dp['P_gF'])/.025
 key=g['catalog']+':'+g['material'];manifest[key]=g
 return {'catalog':g['catalog'],'material':g['material'],'manifest_key':key,'rank':rank,'dispersion_score':float(score),'delta_n_6':delta.tolist(),'weighted_index_rms_difference':float(math.sqrt(np.dot(WEIGHTS,delta**2))),'index_shape_rms_after_weighted_mean_removal':float(math.sqrt(np.dot(WEIGHTS,residual**2))),'delta_nd':float(g['nd_catalog']-old['nd_catalog']),'delta_vd':float(g['vd_computed']-old['vd_computed']),'delta_partial_dispersion':dp,'catalog_relative_cost':g['catalog_relative_cost'],'status_code':g['status_code'],'melt_frequency_code':g['melt_frequency_code'],'stock_verified':False,'price_quote_available':False}

for phase,catalogs in [('mixed',['SCHOTT','CDGM']),('all_cdgm',['CDGM'])]:
 elements=[]
 for e,(surface,old) in enumerate(zip(SURFACES,original),1):
  pool=[g for g in glass if g['catalog'] in catalogs and g['status_code'] in [0,1] and not g['exclude_substitution'] and abs(g['nd_catalog']-old['nd_catalog'])<.045 and abs(g['vd_computed']-old['vd_computed'])<12 and not g['material'].startswith(('D263','AF32','B270')) and not (g['catalog']=='SCHOTT' and ('HT' in g['material'] or re.search(r'G\d',g['material'])))]
  pool=list({g['catalog']+':'+g['material']:g for g in pool}.values())
  ranked=sorted(pool,key=lambda g:candidate(g,old,0)['dispersion_score'])
  # Keep 5 real materials. Mixed includes the unchanged glass and close CDGM
  # alternatives so stages share useful optical substitutions.
  selected=ranked[:5]
  if phase=='mixed':
   if old not in selected:selected=[old]+selected[:4]
   cd=[g for g in ranked if g['catalog']=='CDGM'][:2]
   for g in cd:
    if g not in selected:selected=selected[:4]+[g]
  if len(selected)<3:raise ValueError('Too few candidates '+phase+' '+old['material'])
  selected=sorted(selected,key=lambda g:candidate(g,old,0)['dispersion_score'])
  elements.append({'element':e,'surface':surface,'original':old['material'],'original_catalog':'SCHOTT','candidates':[candidate(g,old,i+1) for i,g in enumerate(selected)]})
 # Baseline + one local move seeds. No 5^6 exhaustive combinations.
 base=[{'catalog':'SCHOTT','material':name} for name in ORIGINAL] if phase=='mixed' else [x['candidates'][0] for x in elements]
 seeds=[];seen=set()
 def add_seed(sequence,reason):
  keys=tuple((x['catalog'],x['material']) for x in sequence)
  if keys in seen:return
  seen.add(keys);seeds.append({'id':phase+'_seed_'+str(len(seeds)+1),'materials':[x['material'] for x in sequence],'catalogs':[x['catalog'] for x in sequence],'change_count':sum(x['catalog']!='SCHOTT' or x['material']!=o for x,o in zip(sequence,ORIGINAL)),'reason':reason})
 add_seed(base,'unchanged reference' if phase=='mixed' else 'closest full-dispersion all-CDGM seed; geometry must be reoptimized')
 if phase=='all_cdgm':add_seed([min((c for c in e['candidates'] if c['catalog_relative_cost']>0),key=lambda c:c['catalog_relative_cost']) for e in elements],'within-CDGM dated OD cost-screening seed; not a quote or verified savings; relaxed geometry must recover performance')
 for i,element in enumerate(elements):
  for g in element['candidates'][:4]:
   changed=base.copy();changed[i]=g;add_seed(changed,'one-element local move from phase seed; two LAK elements are independent')
 if phase=='mixed':add_seed([next(c for c in x['candidates'] if c['catalog']=='CDGM') for x in elements],'all-CDGM bridge seed for second phase')
 phases[phase]={'per_element':elements,'seed_combinations':seeds,'strategy':{'initial_seed_limit':len(seeds),'beam_width':4,'promote_best_seed_count':4,'next_moves':'single-element neighbor changes after geometric relaxation; optional best pair move for cemented elements 4/5','full_cartesian_enumeration':False,'native_requirements':'Load actual named catalog glass, preserve all six spectral wavelengths and weights; common image plane, full105deg, A4/A6 only, all higher0, no overlap; final native dispersion identity check required.'}}

# Include original and only shortlisted materials; remove exploratory manifest
# entries introduced during ranking to keep the consumer file bounded.
needed={'SCHOTT:'+x for x in ORIGINAL}|{c['manifest_key'] for p in phases.values() for e in p['per_element'] for c in e['candidates']}
manifest={k:bykey[k] for k in sorted(needed)}
plan={'schema_version':1,'generated_date':'2026-09-15','surface_order':SURFACES,'original_materials':ORIGINAL,'wavelengths_um':W.tolist(),'weights':WEIGHTS.tolist(),'phases':phases,'catalog_snapshots':snapshots,'manifest_file':'material_manifest.json','primary_sources':sources,'cost_policy':{'absolute_price':None,'savings_percent':None,'cross_vendor_relative_cost_comparison_permitted':False,'ranking':'Optical full-dispersion distance first. Within-CDGM OD may be used as a dated screening proxy, never a procurement quote. Supplier availability and blank diameter remain unverified.'},'warnings':['Catalog inclusion establishes a valid named dispersion model, not current blank stock or a promise to supply.','Local catalogs date from 2022; current manufacturer portals were checked but individual quotes/stock were not.','Full-dispersion closeness does not guarantee preserved MTF after substitution; geometry and focus must be optimized natively.','Do not equate all-CDGM sourcing with a proven lower delivered cost.','CDGM and SCHOTT OD scales may use different reference glasses; cross-vendor OD ratios are not savings.']}
(P/'catalog_plan.json').write_text(json.dumps(plan,indent=2,ensure_ascii=False),encoding='utf-8')
(P/'material_manifest.json').write_text(json.dumps({'schema_version':1,'wavelengths_um':W.tolist(),'weights':WEIGHTS.tolist(),'reference_temperature':'AGF nominal 20C where TD contains 20; thermal correction not applied','dispersion_formula_implementation':{'1':'n^2=A0+A1*l^2+A2*l^-2+A3*l^-4+A4*l^-6+A5*l^-8','2':'n^2=1+sum(Bi*l^2/(l^2-Ci)), AGF interleaved B,C; l in um'},'catalog_snapshots':snapshots,'materials':manifest,'substitution_differences_by_phase':{key:value['per_element'] for key,value in phases.items()},'excluded_records':excluded,'primary_sources':sources,'native_instances_opened':0},indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'materials':len(manifest),'candidate_names':{phase:[[c['catalog']+':'+c['material'] for c in e['candidates']] for e in p['per_element']] for phase,p in phases.items()},'seed_counts':{k:len(v['seed_combinations']) for k,v in phases.items()}},indent=2))
