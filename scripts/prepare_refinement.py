from pathlib import Path
s=Path('SuperSymmarXL/scripts/optimize_revision2.py').read_text()
s=s.replace("'physical_aperture_seed.zmx'","'SuperSymmarXL_150_R2.zmx'")
s=s.replace("x0=np.r_[b0,sys.LDE.GetSurfaceAt(12).Thickness]", """rids=[1,2,3,4,5,6,8,9,10,11,12]
base_r=np.array([sys.LDE.GetSurfaceAt(i).Radius for i in rids])
base_n=np.array([sys.MFE.GetOperandValue(Z.Editors.MFE.MeritOperandType.INDX,i,1,0,0,0,0,0,0) for i in range(1,13)])
x0=np.r_[b0,sys.LDE.GetSurfaceAt(12).Thickness,np.zeros(11)]
def para():
 M=np.eye(2);old=1;ep=0
 for i in range(1,13):
  ss=sys.LDE.GetSurfaceAt(i);nn=base_n[i-1];M=np.array([[1,0],[-(nn-old)/ss.Radius,1]])@M
  if i==7:ep=M[0,1]/M[0,0]
  if i<12:M=np.array([[1,ss.Thickness/nn],[0,1]])@M
  old=nn
 return -1/M[1,0],-M[0,0]/M[1,0],ep
""")
s=s.replace("sys.LDE.GetSurfaceAt(12).Thickness=float(x[5]);return c", "sys.LDE.GetSurfaceAt(12).Thickness=float(x[5])\n for i,rr,vv in zip(rids,base_r,x[6:]):sys.LDE.GetSurfaceAt(i).Radius=float(rr*(1+vv))\n return c")
s=s.replace("gap=.99+sag(-40.465)-sag(-42.216)-added", "gap=.99+sag(sys.LDE.GetSurfaceAt(11).Radius)-sag(asph.Radius)-added")
s=s.replace("glass=4.7+sag(-42.216)+added-sag(-23.818)", "glass=4.7+sag(asph.Radius)+added-sag(sys.LDE.GetSurfaceAt(9).Radius)")
s=s.replace("np.zeros(102),bad*20]", "np.zeros(102),bad*20,np.zeros(14)]")
s=s.replace("score=float(np.sqrt(np.mean(deficit**2)))", "efl,bfl,ep=para();rms=float(np.sqrt(np.mean(deficit**2)));score=float(max(deficit)+.2*rms)")
s=s.replace("if score<best:", "if score<best and abs(efl-148.1)<.1 and abs(bfl-135.9)<.15 and abs(ep-36.6)<.2:")
s=s.replace("'deficit_rmse':best", "'deficit_rmse':rms,'score':best,'efl':efl,'bfl':bfl,'entrance_pupil':ep")
s=s.replace("R/'checkpoint.json'","R/'refinement_checkpoint.json'")
s=s.replace("np.maximum(refs+.01-vals,0),.025*(vals-refs),max(0,.35-gap)*2]", "np.maximum(refs+.01-vals,0)**2/.1,.015*(vals-refs),max(0,.35-gap)*2,max(0,abs(efl-148.1)-.05)*5,max(0,abs(bfl-135.9)-.08)*5,max(0,abs(ep-36.6)-.1)*2,x[6:]*.1]")
s=s.replace("steps=np.array([2e-5]*5+[.001])", "steps=np.array([2e-5]*5+[.001]+[5e-6]*11)")
s=s.replace("cols=[]\n for i,h in enumerate(steps):\n  xp=x.copy();xm=x.copy();xp[i]+=h;xm[i]-=h;cols.append((fun(xp)-fun(xm))/(2*h))", "cols=[];f0=fun(x)\n for i,h in enumerate(steps):\n  xp=x.copy();xp[i]+=h;cols.append((fun(xp)-f0)/h)")
s=s.replace("bounds=([-.8]*5+[134.5],[.8]*5+[137]),x_scale=[.01]*5+[.1],max_nfev=45", "bounds=([-.8]*5+[134.5]+[-.03]*11,[.8]*5+[137]+[.03]*11),x_scale=[.01]*5+[.1]+[.01]*11,max_nfev=25")
s=s.replace("'SuperSymmarXL_150_R2.zmx'));(R/'optimization.json'", "'SuperSymmarXL_150_R2_refined.zmx'));(R/'refinement.json'")
Path('SuperSymmarXL/scripts/refine_revision2.py').write_text(s)
