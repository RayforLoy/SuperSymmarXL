from pathlib import Path
s=Path('SuperSymmarXL/scripts/fit_round3.py').read_text()
s=s.replace("json.loads((ROOT/'analysis'/'fit_round2.json').read_text())['x'],0.0,0.0", "json.loads((ROOT/'analysis'/'fit_round3.json').read_text())['x']")
needle='r=least_squares('
idx=s.index(needle)
s=s[:idx]+'''steps=np.array([.0001,.001,.002,.001,.005]+[2e-6]*11+[.01,.01])
def jac(x):
 cols=[]
 for i,h in enumerate(steps):
  xp=x.copy();xm=x.copy();xp[i]+=h;xm[i]-=h
  cols.append((fun(xp)-fun(xm))/(2*h))
 return np.array(cols).T
'''+s[idx:]
s=s.replace("diff_step=1e-3,x_scale=", "jac=jac,x_scale=").replace('max_nfev=100','max_nfev=35')
Path('SuperSymmarXL/scripts/fit_round4.py').write_text(s)
