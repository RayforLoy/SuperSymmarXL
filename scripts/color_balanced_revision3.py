"""Weak paraxial color and focus regularization, native FFT objective unchanged."""
import numpy as np
import optimize_revision3 as core
original_initialize=core.initialize
original_evaluate=core.evaluate
def initialize(*args):
 global index,weights
 original_initialize(*args)
 index=np.array([[core.sys.MFE.GetOperandValue(core.Z.Editors.MFE.MeritOperandType.INDX,i,w,0,0,0,0,0,0) for i in range(1,13)] for w in range(1,7)])
 weights=np.array([core.sys.SystemData.Wavelengths.GetWavelength(w).Weight for w in range(1,7)]);weights/=weights.sum()
def evaluate(x,save=None):
 residual,v=original_evaluate(x,save)
 bf=[]
 for ns in index:
  matrix=np.eye(2);old=1.
  for i,n in enumerate(ns,1):
   s=core.sys.LDE.GetSurfaceAt(i)
   matrix=np.array([[1.,0.],[-(n-old)/s.Radius,1.]])@matrix
   if i<12:matrix=np.array([[1.,s.Thickness/n],[0.,1.]])@matrix
   old=n
  bf.append(-matrix[0,0]/matrix[1,0])
 bf=np.array(bf);std=float(np.sqrt(np.dot(weights,(bf-np.dot(weights,bf))**2)))
 v['weighted_paraxial_bfl_std_mm']=std
 return residual+[max(0,std-.20)*4,max(0,abs(v['best_focus_minus_paraxial_bfl_mm'])-.25)*.5],v
core.initialize=initialize;core.evaluate=evaluate
if __name__=='__main__':core.main()
