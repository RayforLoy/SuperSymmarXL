from pathlib import Path
exec(Path(__file__).with_name('fit_physical.py').read_text().split('count=0;')[0])
from scipy.optimize import differential_evolution
for i in range(13,18):asph.GetCellAt(i).DoubleValue=0
count=0;best=1
# Low-order alternative: a conic, avoiding unconstrained high-order edge excursions.
def cost(x):
 global count,best
 asph.Conic=float(x[0]);sys.LDE.GetSurfaceAt(12).Thickness=float(x[1]);err=np.concatenate([(calc(fn)-target[fn]).ravel() for fn in target]);value=float(np.sqrt(np.mean(err**2)));count+=1
 if value<best:
  best=value;(ROOT/'analysis'/'conic_checkpoint.json').write_text(json.dumps({'conic':float(x[0]),'focus':float(x[1]),'rmse':best,'count':count},indent=2))
 if count%20==1:print('conic',count,best,flush=True)
 return value
r=differential_evolution(cost,[(-5,1),(133,138)],seed=5870234,popsize=6,maxiter=20,tol=.003,polish=False)
asph.Conic=float(r.x[0]);sys.LDE.GetSurfaceAt(12).Thickness=float(r.x[1]);out={fn:calc(fn).tolist() for fn in target};sys.SystemData.Aperture.ApertureValue=148.1/5.6
sys.SaveAs(str(ROOT/'models'/'conic_constrained.zmx'));(ROOT/'analysis'/'conic_result.json').write_text(json.dumps({'x':r.x.tolist(),'outputs':out,'rmse':r.fun},indent=2));a.Close();app.CloseApplication()
