from pathlib import Path
import json,hashlib
p=Path(__file__).resolve().parents[1]
records=[]
for f in p.glob('*.pdf'):
 records.append({'file':f.name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'source':'user-provided local PDF'})
(p/'reference'/'sources.json').write_text(json.dumps({'files':records,'web_sources':[{'url':'https://patents.google.com/patent/US5870234A/en','role':'Patent identity verification; actual prescription transcribed from local patent PDF'},{'url':'https://www.schott.com/en-us/products/optical-glass-p1000267/downloads','role':'Manufacturer catalog portal; stock and quotation not verified'}],'glass_catalog':r'C:\Users\liuru\Documents\Zemax\Glasscat\SCHOTT.AGF','glass_catalog_sha256':hashlib.sha256(Path(r'C:\Users\liuru\Documents\Zemax\Glasscat\SCHOTT.AGF').read_bytes()).hexdigest()},indent=2))
