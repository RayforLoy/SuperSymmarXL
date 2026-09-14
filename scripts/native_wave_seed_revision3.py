"""Native smooth wavefront search as an independent candidate generator."""
from pathlib import Path
import argparse,json,numpy as np
import optimize_revision3 as core
p=argparse.ArgumentParser();p.add_argument('--seed',required=True);p.add_argument('--name',required=True);p.add_argument('--data',type=int,default=1);a=p.parse_args()
core.initialize(a.seed,128,str(core.R/'target_optimization.json'),True,True)
try:
 f=core.sys.SystemData.Fields
 while f.NumberOfFields>1:f.RemoveField(f.NumberOfFields)
 f.GetField(1).Weight=1
 for h in [.1,.3,.5,.68,1]:f.AddField(0,float(np.degrees(np.arctan(h*193/148.1))) if h<1 else 52.5,.3 if h<1 else 0)
 core.sys.SystemData.Aperture.ApertureValue=148.1/5.6
 for i in range(13,20):core.sys.LDE.GetSurfaceAt(10).GetCellAt(i).MakeSolveVariable()
 core.sys.LDE.GetSurfaceAt(12).ThicknessCell.MakeSolveVariable()
 w=core.sys.MFE.SEQOptimizationWizard
 print('Wizard',[(q.Name,str(q.PropertyType)) for q in w.GetType().GetProperties()],flush=True)
 print('Wizard methods',[q.Name for q in w.GetType().GetMethods() if not q.Name.startswith(('get_','set_'))],flush=True)
 w.Data=a.data;w.Type=0;w.OverallWeight=1;w.Ring=5;w.StartAt=1;w.Apply()
 print('Operands',core.sys.MFE.NumberOfOperands,[(i,str(core.sys.MFE.GetOperandAt(i).Type)) for i in range(1,min(8,core.sys.MFE.NumberOfOperands)+1)],flush=True)
 o=core.sys.Tools.OpenLocalOptimization();o.Cycles=core.Z.Tools.Optimization.OptimizationCycles.Automatic
 o.RunAndWaitForCompletion();print('Native merit',o.CurrentMeritFunction,flush=True);o.Close()
 core.sys.Tools.RemoveAllVariables();core.sys.SaveAs(str(core.R/(a.name+'_raw.zmx')))
finally:core.app.CloseApplication()
# The shared five-term evaluator cannot represent A14/A16; retain these in the
# native file, zero their optimizer changes, and compute geometry separately.
core.initialize(str(core.R/(a.name+'_raw.zmx')),128,str(core.R/'target_optimization.json'),True,True)
try:
 residual,v=core.evaluate(np.zeros(28),str(core.R/(a.name+'.zmx')))
 v['native_extra_asphere']={str(i):core.sys.LDE.GetSurfaceAt(10).GetCellAt(i).DoubleValue for i in [18,19]}
 (core.R/(a.name+'.json')).write_text(json.dumps(v,indent=2))
 print('Native MTF max shortfall',v['max_shortfall'],'gap',v['geometry_gaps'],flush=True)
finally:core.app.CloseApplication()
