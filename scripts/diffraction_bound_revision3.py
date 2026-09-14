from pathlib import Path
import numpy as np,json
R=Path(__file__).resolve().parents[1]/'revision3'
wavelengths=np.array([546,644,588,480,436,405])*1e-6
weights=np.array([24.6,18.6,22.1,12.4,15.2,7.1])/100
results={}
for fn in [5.6,8,22]:
 values=[]
 for frequency in [5,10,20]:
  s=np.clip(fn*frequency*wavelengths,0,1)
  values.append(float(np.dot(weights,2/np.pi*(np.arccos(s)-s*np.sqrt(1-s*s)))))
 results[str(fn)]={'frequencies_lp_mm':[5,10,20],'mtf':values}
out={'method':'Polychromatic weighted incoherent diffraction MTF for an unaberrated, unvignetted circular pupil in air; normalized frequency lambda_mm*f_number*lp_per_mm. This is an axis reference for this pupil shape, not a strict universal off-axis/apodized-pupil bound.','wavelengths_nm':[546,644,588,480,436,405],'weights_percent':[24.6,18.6,22.1,12.4,15.2,7.1],'results':results}
(R/'diffraction_reference.json').write_text(json.dumps(out,indent=2))
print(json.dumps(results,indent=2))
