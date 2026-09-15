from pathlib import Path
import json,csv,hashlib
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
R=Path('D:\\_Camera\\LensRebuild\\SuperSymmarXL\\overnight_20260915\\cdgm')
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
 names={catalog:catalog_materials(catalog) for catalog in catalog_ids}
 cdgm_catalogs=[catalog for catalog in catalog_ids if catalog.upper()=='CDGM']
 cdgm_names=set()
 for catalog in cdgm_catalogs:cdgm_names.update(catalog_materials(catalog))
 historical=json.loads((ROOT/'revision2'/'validated.json').read_text(encoding='utf-8'))
 previous={int(s['surface']):s['glass'] for s in historical['surfaces']}
 elements=[]
 for element,i in enumerate([1,3,5,8,9,11],1):
  material=str(sys.LDE.GetSurfaceAt(i).Material)
  solve=str(sys.LDE.GetSurfaceAt(i).MaterialCell.GetSolveData().Type)
  assert solve in ['Fixed','None'],'Material must resolve through a fixed catalog, not a model/offset/substitution solve'
  # A glass name can also exist in unrelated installed catalogs.  Resolution
  # ambiguity is determined only among catalogs actually loaded by this file.
  containing=[catalog for catalog in in_use if catalog and material in names[catalog]]
  elements.append({'element':element,'surface':i,'historical_reference_glass':previous[i],
   'native_material':material,'native_material_solve':solve,'catalogs_in_use_containing_material':containing,
   'member_of_available_CDGM_catalog':material in cdgm_names,
   'unambiguous_CDGM_resolution':bool(containing) and all(c.upper()=='CDGM' for c in containing)})
 print('CATALOG_DIAGNOSTIC',json.dumps({'available':available,'in_use':in_use,'cdgm_catalogs':cdgm_catalogs,
  'cdgm_material_count':len(cdgm_names),'elements':elements},ensure_ascii=True),flush=True)
 assert all(row['native_material'] and row['catalogs_in_use_containing_material'] for row in elements),'Unresolved or modeled material cannot certify catalog identity'
 all_cdgm=bool(cdgm_catalogs) and all(row['member_of_available_CDGM_catalog'] and row['unambiguous_CDGM_resolution'] for row in elements)
 if 'cdgm'=='cdgm':assert all_cdgm,'CDGM phase requires all six native materials to resolve unambiguously through CDGM catalogs in use'
 result={'phase':'cdgm','source_sha256':v['source_sha256'],'model_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),
  'available_catalogs':available,'catalogs_in_use':in_use,'elements':elements,'all_six_native_materials_CDGM':all_cdgm,
  'quotation_status':'No verified supplier quote, cost savings, availability, batch precision, cost or delivery commitment.'}
 (R/'material_catalog_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 with (R/'material_comparison.csv').open('w',newline='',encoding='utf-8-sig') as f:
  writer=csv.DictWriter(f,fieldnames=list(elements[0]));writer.writeheader();writer.writerows(elements)
 print('Verified six native material/catalog identities; all CDGM:',all_cdgm,flush=True)
finally:app.CloseApplication()
