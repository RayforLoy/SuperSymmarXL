exec(open(__file__.replace('seed_optimize.py','probe_zos.py')).read().split("print('system'")[0])
import json
sys.LoadFile(str(ROOT/'models'/'patent_baseline.zmx'),False)
sys.LDE.GetSurfaceAt(7).SemiDiameter=13.9984
sys.SystemData.RayAiming.RayAiming=Z.SystemData.RayAimingMethod.Real
while sys.SystemData.Fields.NumberOfFields>8:sys.SystemData.Fields.RemoveField(sys.SystemData.Fields.NumberOfFields)
q=sys.Tools.OpenQuickFocus();q.RunAndWaitForCompletion();q.Close()
print('focus',sys.LDE.GetSurfaceAt(12).Thickness,flush=True)
for i in [13,14,15]:sys.LDE.GetSurfaceAt(10).GetCellAt(i).MakeSolveVariable()
sys.LDE.GetSurfaceAt(12).ThicknessCell.MakeSolveVariable()
for j in range(1,9):sys.SystemData.Fields.GetField(j).Weight=1 if j==1 else .1
wiz=sys.MFE.SEQOptimizationWizard;wiz.Data=1;wiz.OverallWeight=1;wiz.Ring=3;wiz.Apply()
opt=sys.Tools.OpenLocalOptimization();opt.Cycles=Z.Tools.Optimization.OptimizationCycles.Automatic;opt.RunAndWaitForCompletion();print('merit',opt.CurrentMeritFunction);opt.Close()
print('focus/asphere',sys.LDE.GetSurfaceAt(12).Thickness,[sys.LDE.GetSurfaceAt(10).GetCellAt(i).DoubleValue for i in [13,14,15]])
sys.SaveAs(str(ROOT/'models'/'seed_optimized.zmx'));app.CloseApplication()

