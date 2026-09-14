from pathlib import Path
import json,hashlib,math,pymupdf
P=Path('SuperSymmarXL')
files=[P/'models'/('SuperSymmarXL_150_f'+f+'_reverse.zmx') for f in ['5p6','8','22']]+list((P/'reports').glob('*.pdf'))+[P/'analysis/mtf_comparison.png',P/'analysis/mtf_comparison.csv',P/'analysis/validated_results.json',P/'README.md']
manifest=[]
for f in files:
 assert f.exists() and f.stat().st_size>0
 manifest.append({'file':str(f.relative_to(P)),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
for f in (P/'reports').glob('*.pdf'):
 d=pymupdf.open(f);assert len(d)>0 and all(len(pg.get_text())>0 for pg in d)
v=json.loads((P/'analysis/validated_results.json').read_text());assert v['verified_sampling']=={'5.6':2048,'8':512,'22':512}
assert all(math.isfinite(x) and 0<=x<=1 for rows in v['results'].values() for row in rows for x in row)
(P/'analysis/delivery_manifest.json').write_text(json.dumps(manifest,indent=2))
print('Verified',len(files),'delivery files; numerical samples finite; PDFs readable.')
print('Root entries:',[x.name for x in Path('.').iterdir()])
