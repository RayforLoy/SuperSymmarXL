from pathlib import Path
p=Path('SuperSymmarXL/scripts/fit_round2.py');s=p.read_text()
s=s.replace("x0=np.array(json.loads((ROOT/'analysis'/'fit_round1.json').read_text())['x'])", "x0=np.r_[json.loads((ROOT/'analysis'/'fit_round2.json').read_text())['x'],0.0,0.0]\n")
s=s.replace("bounds=([-30,-100,-100,132,.4]+[-.03]*len(base_r),[30,100,100,140,5.66]+[.03]*len(base_r))", "bounds=([-30,-100,-100,132,.4]+[-.05]*len(base_r)+[-100,-100],[30,100,100,140,5.66]+[.05]*len(base_r)+[100,100])")
s=s.replace('def apply(x):','def apply(x):\n asph.GetCellAt(16).DoubleValue=float(x[-2]*1e-15)\n asph.GetCellAt(17).DoubleValue=float(x[-1]*1e-18)')
s=s.replace("res.extend(x[5:]*.3)","res.extend(x[5:16]*.1)")
s=s.replace("r=least_squares(fun,x0,bounds=bounds,diff_step=.01,x_scale='jac',max_nfev=120,verbose=0,ftol=1e-6,xtol=1e-7)","r=least_squares(fun,x0,bounds=bounds,diff_step=1e-3,x_scale=np.array([1,2,5,1,1]+[.01]*11+[5,5]),max_nfev=100,verbose=0,ftol=1e-7,xtol=1e-8)")
p.with_name('fit_round3.py').write_text(s)
