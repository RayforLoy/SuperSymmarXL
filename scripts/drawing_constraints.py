from pathlib import Path
import json,numpy as np
P=Path(__file__).resolve().parents[1]/'revision2'
z=np.cumsum([0,3.4,13,16.03,11.636,3.2,4.8399010321,1.2200989679,13.1,4.7,.99,5.3])
x=np.array([266.5,287,370,472,546,566,597,605,688,718,724,757])
a,b=np.polyfit(z,x,1)
d={'source':'super-symmar_xl_56_150.pdf page 1 upper-right section; 6x rendered crop reference_section.png','method':'Manual axial vertex positions; least-squares common scale against patent embodiment 1 plus pupil-derived stop. Drawing is not certified dimensional production data.','scale_pixels_per_mm':a,'origin_pixel':b,'axial_residual_rms_mm':float(np.sqrt(np.mean((x-(a*z+b))**2))/a),'vertices_mm':z.tolist(),'vertices_pixel':x.tolist(),'clear_semidiameters_mm':{1:41,2:29,3:25.8,4:19.5,5:15,6:14.5,8:14.4,9:14.4,10:15.5,11:14,12:18.8},'assumed_clear_radius_readout_uncertainty_mm':.3,'max_semi_field_angle_deg':52.5,'mtf_reference_max_image_height_mm':193}
(P/'drawing_constraints.json').write_text(json.dumps(d,indent=2));print(a,d['axial_residual_rms_mm'])
