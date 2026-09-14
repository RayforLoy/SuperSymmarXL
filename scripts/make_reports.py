from pathlib import Path
import json, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.utils import ImageReader
import html,textwrap
P=Path(__file__).resolve().parents[1]
v=json.loads((P/'analysis/validated_results.json').read_text()); t=json.loads((P/'analysis/target_manual.json').read_text())
dense=json.loads((P/'analysis/dense_mtf.json').read_text()) if (P/'analysis/dense_mtf.json').exists() else None
colors=['#1767a6','#d56a16','#28936b']
fig,axs=plt.subplots(1,3,figsize=(15,5),sharey=True)
errors={}
for ax,fn in zip(axs,['5.6','8','22']):
 y=np.array(v['results'][fn]);ref=np.array(t['data'][fn]);h=np.array(t['heights'][:len(y)])*100;e=y-ref
 errors[fn]={'rmse':float(np.sqrt(np.mean(e*e))),'max_abs':float(np.max(np.abs(e)))}
 for k,f in enumerate([5,10,20]):
  for j,dr in enumerate(['T','S']):
   ls='--' if j==0 else '-'
   if dense:
    dd=dense[fn][k];xx=np.array(dd['x'])*{'5.6':.68,'8':.78,'22':1}[fn]*100;yy=np.array(dd['y'])[:,j];ax.plot(xx,yy,ls,color=colors[k],label=f'{f} lp/mm {dr}')
   else:ax.plot(h,y[:,2*k+j],ls,color=colors[k],label=f'{f} lp/mm {dr}')
   if j==0:ax.scatter(h,ref[:,2*k+j],marker='x',color=colors[k],s=27)
  else:ax.scatter(h,ref[:,2*k+j],marker='o',facecolors='none',edgecolors=colors[k],s=27)
 ax.set(title=f'f/{fn} | RMSE {errors[fn]["rmse"]:.3f}',xlabel='Relative image height (%)',xlim=(0,100),ylim=(0,1));ax.grid(alpha=.25)
axs[0].set_ylabel('MTF');axs[2].legend(ncol=2,fontsize=8)
fig.suptitle('Super-Symmar XL 150 reverse model | lines: OpticStudio FFT 512 | markers: manual reference')
fig.tight_layout();fig.savefig(P/'analysis/mtf_comparison.png',dpi=180);plt.close(fig)
allerr=np.concatenate([(np.array(v['results'][fn])-t['data'][fn]).ravel() for fn in ['5.6','8','22']])
overall={'rmse':float(np.sqrt(np.mean(allerr**2))),'max_abs':float(np.max(np.abs(allerr)))}
(P/'analysis/acceptance.json').write_text(json.dumps({'criteria':'Proposed engineering screen, not Schneider specification: RMSE <= 0.05 and max absolute error <= 0.12; manual extraction uncertainty 0.02-0.04; infinity only','per_aperture':errors,'overall':overall,'pass':all(e['rmse']<=.05 and e['max_abs']<=.12 for e in errors.values())},indent=2))
sur=v['surfaces'];pos=np.cumsum([0]+[d['thickness_mm'] for d in sur[:-1]])
def sag(d,r):
 R=d['radius_mm'];base=np.zeros_like(r) if np.isinf(R) else r*r/(R*(1+np.sqrt(np.maximum(0,1-r*r/(R*R)))))
 if d['surface']==10:
  for a,k in zip(v['asphere_A4_A6_A8_A10_A12'],[4,6,8,10,12]):base+=a*r**k
 return base
fig,ax=plt.subplots(figsize=(12,5))
edge=[]
for i,d in enumerate(sur[:-1]):
 if not d['glass']:continue
 dn=sur[i+1];r=min(d['semi_diameter_mm'],dn['semi_diameter_mm'],abs(d['radius_mm'])*.98,abs(dn['radius_mm'])*.98)
 yy=np.linspace(-r,r,301);left=pos[i]+sag(d,yy);right=pos[i+1]+sag(dn,yy)
 ax.add_patch(Polygon(np.c_[np.r_[left,right[::-1]],np.r_[yy,yy[::-1]]],fc='#c4e3f4',ec='#1c4056',lw=1))
 ax.text((pos[i]+pos[i+1])/2,-r-5,d['glass'],ha='center',rotation=45,fontsize=8)
 edge.append({'front_surface':i+1,'assessment_radius_mm':r,'min_axial_thickness_in_common_aperture_mm':float(np.min(right-left))})
ax.axhline(0,color='gray',lw=.5);ax.axvline(pos[6],color='#d56a16',lw=1,label='Stop plane');ax.set_aspect('equal');ax.autoscale();ax.set(xlabel='Axial distance (mm)',ylabel='Height (mm)',title='Reverse-model optical section; clear-aperture estimate, no mechanical housing');ax.legend();fig.tight_layout();fig.savefig(P/'analysis/lens_section.png',dpi=180);plt.close(fig)
(P/'analysis/geometry_screen.json').write_text(json.dumps(edge,indent=2))
air=[]
for i,d in enumerate(sur[:-1]):
 if d['glass'] or d['stop'] or sur[i+1]['stop']:continue
 dn=sur[i+1];r=min(d['semi_diameter_mm'],dn['semi_diameter_mm'],abs(d['radius_mm'])*.98,abs(dn['radius_mm'])*.98)
 rr=np.linspace(0,r,1001);gap=d['thickness_mm']+sag(dn,rr)-sag(d,rr)
 air.append({'after_surface':i+1,'assessment_radius_mm':r,'min_axial_air_gap_mm':float(min(gap))})
(P/'analysis/air_gap_screen.json').write_text(json.dumps(air,indent=2))
airmin=min(x['min_axial_air_gap_mm'] for x in air)
r_asph=min(sur[9]['semi_diameter_mm'],sur[10]['semi_diameter_mm'])
rr=np.linspace(0,r_asph,1001)
depart=sum(a*rr**k for a,k in zip(v['asphere_A4_A6_A8_A10_A12'],[4,6,8,10,12]))
slope=sum(k*a*rr**(k-1) for a,k in zip(v['asphere_A4_A6_A8_A10_A12'],[4,6,8,10,12]))
(P/'analysis/asphere_geometry.json').write_text(json.dumps({'evaluated_radius_mm':r_asph,'max_abs_departure_from_vertex_sphere_mm':float(max(abs(depart))),'max_abs_departure_slope':float(max(abs(slope)))},indent=2))
conic=json.loads((P/'analysis/conic_result.json').read_text())
physical=json.loads((P/'analysis/physical_result.json').read_text())
physical_rmse=float(np.sqrt(np.mean(np.concatenate([(np.array(physical['outputs'][fn])-t['data'][fn]).ravel() for fn in ['5.6','8','22']])**2)))
passed=all(e['rmse']<=.05 and e['max_abs']<=.12 for e in errors.values())
status='在选定的无限远离散采样点上通过拟合误差筛选。' if passed else '尚未达到“MTF 基本相同”的筛选门槛；这是逆向候选模型，不能标为原厂等效设计。'
metric='\n'.join(f"- f/{fn}：RMSE {100*e['rmse']:.2f} 个百分点；最大偏差 {100*e['max_abs']:.2f} 个百分点。" for fn,e in errors.items())
fo=v['first_order'];a4,a6,a8,a10,a12=v['asphere_A4_A6_A8_A10_A12']
opt=f'''# Super-Symmar XL 150 mm f/5.6 逆向光学性能报告

状态：{status}

## 交付与来源
主模型为 models/SuperSymmarXL_150_f5p6_reverse.zmx，另附 f/8、f/22 版本。模型由本机 Ansys Zemax OpticStudio 2023 R1 的 ZOS-API 建立和复算。它是依据公开专利和原厂扫描数据拟合得到的工程处方，不是施耐德原始生产处方。

采用用户提供的 super-symmar_xl_56_150.pdf 第 1、2 页，以及 US5870234 第一实施例。原始文件校验值见 reference/sources.json。专利未公开非球面系数、明确玻璃牌号、有效口径和光阑精确位置；光阑位置可利用原厂瞳位置另行反求，但不应视为实物测量值。

## 原厂目标与计算条件
原厂标注实际焦距 148.1 mm、后焦距 135.9 mm、光学总长 77.4 mm、最大像高约 193 mm。原厂无限远 MTF 频率为 5、10、20 lp/mm；径向实线对应弧矢 S，虚线对应子午 T。

采用原厂波长 546、644、588、480、436、405 nm，权重依次为 24.6、18.6、22.1、12.4、15.2、7.1%。统一平面像面、无限远物距、真实光线瞄准；入瞳直径按 148.1/F 设置。采用无镀膜偏振加权的标量 FFT MTF。原厂聚焦说明为 f/5.6、轴上 20 lp/mm 最大值；本轮用统一像面参与多光圈拟合，并未强制精确复现该聚焦程序，这仍是一项模型条件差异。

原厂扫描图经人工近似读数，预计约 ±2–4 个百分点不确定度。这里只验证无限远曲线；原厂另外给出的 -0.1、-0.2 倍率尚未拟合。全开和 f/8 的目标点取到 68% 像高，f/22 取到 100%，不能据此声称全开覆盖全部 386 mm 像圈均有同等像质。

## MTF 对比
预先采用的工程筛选线为每档光圈 RMSE ≤5 个百分点、最大绝对偏差 ≤12 个百分点；这不是施耐德发布的允差。该筛选衡量离散目标拟合，不能代替独立实物验证。

{metric}

总体 RMSE 为 {100*overall['rmse']:.2f} 个百分点，最大偏差为 {100*overall['max_abs']:.2f} 个百分点。完整数值（f/5.6 为 2048，f/8 与 f/22 为 512）见 analysis/mtf_comparison.csv，叠图见 analysis/mtf_comparison.png。叠图曲线取自原生 512 采样的 MTF 随视场分析；定量误差使用独立固定视场复算。原生扫描覆盖 f/5.6 的 0–68%、f/8 的 0–78%、f/22 的 0–100% 像高；扫描曲线不等于所有中间点都有独立原厂对照数据。512×512 相对 256×256 的最大变化分别为 {', '.join(fn+': '+format(100*x,'.3f')+' 个百分点' for fn,x in v['convergence_256_512'].items())}。f/8、f/22 的定量结果采用 512 采样且无采样警告。f/5.6 的 512 原生输出曾报告“取样太低，数据不准确”，故补做 1024/2048 复核：更高采样输出已无该警告，1024 与 2048 的最大变化为 {100*v["convergence_1024_2048_f5p6"]:.4f} 个百分点。最终 f/5.6 定量误差采用 2048 结果，其与 512 的最大变化为 {100*v["convergence_512_2048_f5p6"]:.4f} 个百分点。复核数据见 high_sampling_check.json 和 native_MTF_f5.6_1024/2048.txt。

## 处方与一阶性能
采用 6 片 5 组，第四组胶合，模型第 7 面为光阑，第 10 面为偶次非球面。面号包含新增光阑，故第 10 面对应专利第 9 光学面。

主波长有效焦距 {fo['EFFL']:.5f} mm；独立近轴矩阵给出的后焦距 {fo['wave_1']['bfl']:.5f} mm；实际像面到最后面的距离 {sur[-1]['thickness_mm']:.5f} mm；首面到末面顶点总长 {sum(d['thickness_mm'] for d in sur[:-1]):.5f} mm。近轴后焦距与实际最佳像面位置是不同量。入瞳位置计算值 {fo["ENPP"]:.5f} mm（原厂 36.6 mm），出瞳相对末面的计算位置 {fo["EXPP"]+sur[-1]["thickness_mm"]:.5f} mm（原厂 -16.1 mm）。

补充约束：在未改变专利曲率/厚度时，用原厂入瞳位置可反求光阑位于第三片后表面后 4.839901 mm，且出瞳计算为 -16.14464 mm。physical_constrained.zmx 保留了按这一约束重拟合的候选；主交付仍按已完成的 MTF 对比结果选择。

非球面定义 z(r)=c r²/[1+sqrt(1-c²r²)]+A4 r⁴+A6 r⁶+A8 r⁸+A10 r¹⁰+A12 r¹²，圆锥常数为零，长度单位 mm。A4={a4:.12g} mm^-3，A6={a6:.12g} mm^-5，A8={a8:.12g} mm^-7。A10={a10:.12g} mm^-9，A12={a12:.12g} mm^-11。其余高阶项为零。完整曲率、厚度及玻璃见 analysis/prescription.csv。

玻璃通过专利的 ne/ve 选择接近的 SCHOTT 全色散模型：KF9、N-LAK33B、N-LAK33B、N-SK5、F2、K10。专利是 e 线指标，不能直接把 ne 当作 Zemax 模型玻璃的 nd。所用目录版本及散列已记录，玻璃与历史熔次之间的偏差尚未得到实物验证。

## 尚未证实的性能
畸变的主光线计算见 validated_results.json，不能替代原厂多倍率畸变图的完整验收。照度、透射率、镀膜、鬼像、杂散光、温漂、有限物距性能及精确机械遮挡没有完成等效验证。自动口径与公开剖面图尚未建立可制造的完整尺寸链。

补充候选比较：严格保留专利尺寸并由瞳位置约束光阑的高阶非球面候选，整体离散 MTF RMSE 约 {100*physical_rmse:.2f} 个百分点；低阶纯圆锥面候选的整体 RMSE 约 {100*conic["rmse"]:.2f} 个百分点。这些替代尝试也未解决全部目标。另行限制第三片通光半径的试算仍保留约 11 个百分点的全开 RMSE，故未据此替换主候选。

主波长近轴畸变样点（像高 mm / 百分比）为：{", ".join(format(d["height_mm"],".1f")+" / "+format(d["distortion_pct"],".3f") for d in v["distortion"])}。六波长近轴后焦距最大跨度约 {max(fo["wave_"+str(i)]["bfl"] for i in range(1,7))-min(fo["wave_"+str(i)]["bfl"] for i in range(1,7)):.4f} mm；这是近轴色焦移指标，不是实测最佳焦面色差。

MTF 拟合存在非唯一性。即使曲线通过上述筛选，也只说明该候选在已采样条件下接近目标，不能证明内部结构、其他视场、其他倍率或实物性能与原厂相同。
'''
maxsens=max(v['sensitivity'],key=lambda x:x['mtf_max_change'])
prod=f'''# Super-Symmar XL 150 mm f/5.6 生产可能性报告

结论：当前候选未通过按现有有效口径的几何制造筛查，非球面后的最小空气间隔为 {airmin:.4f} mm，出现表面交叠。必须先修订处方或有效口径并重新验证覆盖范围，不能据此加工装配或作出良率保证。MTF 状态：{status}

## 结构与工艺
候选结构为 6 片 5 组、1 个胶合界面、1 个玻璃非球面，中央机械光阑。可考虑玻璃毛坯加工、球面研磨抛光、非球面数控加工及修形、检测、清洗镀膜、胶合与定心装调。这里是工艺路线评估，没有工厂报价或设备能力承诺。

非球面位于胶合组后外表面，对同轴度、面形和面形测量要求较高。在半径 {r_asph:.3f} mm 内，相对顶点参考球面的最大绝对偏离约 {1000*max(abs(depart)):.1f} μm，偏离项最大斜率约 {max(abs(slope)):.5f}。这不是最佳拟合球面（BFS）偏离。应先落实干涉测量的补偿器/CGH 或经校准轮廓仪方案，再确定加工公差。不能单凭 非球面系数数值推断供应商能保证量产一致性。lens_section.png 仅是光学剖面，不能用作镜筒加工图。

## 材料采购
KF9 是本机 SCHOTT 历史目录中的旧玻璃记录；N-LAK33B、N-SK5、F2、K10 已有目录数据，但目录存在不等于当前库存或可订制尺寸。采购前须取得指定熔次、尺寸、均匀性、气泡条纹和交期的书面确认。官方资料入口：https://www.schott.com/en-us/products/optical-glass-p1000267/downloads 。

不能只按 nd、vd 做无重优化的玻璃替换。尤其含高折射率正片和胶合组，应比较整个 405–644 nm 的折射率、部分色散、热膨胀、化学耐久性及胶合应力。N-KF9 替代 KF9、无铅玻璃替代 F2 等方案均需要重新追迹和试片，本报告未验证替换结果。

## 几何可行性筛查
分析脚本对相邻玻璃表面公共有效半径内的轴向厚度进行了检查，结果见 analysis/geometry_screen.json；最小值为 {min(x['min_axial_thickness_in_common_aperture_mm'] for x in edge):.4f} mm。该计算只针对旋转对称处方及公共光学口径，未覆盖镜片台阶、倒边、外径、压圈、胶层和所有温度装配间隙。模型半口径包含软件自动估计，不应直接等同于量产外径。

空气间隔另行检查（不含与光阑面相接的段），公共半径范围内的最小轴向间隔为 {airmin:.4f} mm，逐段结果见 air_gap_screen.json。负值表示按当前口径存在表面交叠，必须修订非球面、间距或有效口径；在消除这一问题前不能释放生产。

## 装配与制造敏感性
已进行了 f/22 下无补偿的单项扰动：像面 ±0.05 mm，首面半径 ±0.1%，第二片和胶合组厚度 ±0.02 mm，两个空气间隔 ±0.02 mm。最大 MTF 变化来自 {maxsens['parameter']}（面 {maxsens['surface']}，扰动 {maxsens['delta_mm']:.5f} mm），变化幅度 {100*maxsens['mtf_max_change']:.2f} 个百分点。全部结果见 validated_results.json 的 sensitivity。

这些是探索性扰动幅度，不是合格制造公差；它们也不是 Monte Carlo 良率分析。尚未覆盖偏心、倾斜、楔角、折射率熔次误差、非球面面形误差、胶层、镀膜或温度影响。因此不能给出良率百分比、生产成本或交付周期。

## 建议的样机阶段与放行条件
1. 完成原厂 MTF 读数复核、全视场/有限倍率复算、聚焦条件核对，达到明确约定的验收误差。
2. 以实物测量或更完整资料收敛有效口径、光阑位置、外径和镜筒尺寸链，冻结可制造处方。
3. 获取玻璃熔次数据，完成替代材料验证、完整公差分析及有补偿的 Monte Carlo 预测；确定调焦与组间距调整量。
4. 向具备非球面加工检测能力的工厂询价，明确面形、表面质量、偏心、胶合和镀膜检验方法。
5. 制作小批样机并测量六波长或经约定等效光谱条件下的 MTF、畸变和照度；以实测结果决定设计修订和是否放行。

当前建议为“先消除表面交叠并重新拟合，随后才考虑样机验证”，不建议按本轮逆向处方直接批量投产。
'''
for name,body in [('光学性能报告',opt),('生产可能性报告',prod)]:
 (P/'reports'/f'{name}.md').write_text(body,encoding='utf-8')
 # Readable self-contained PDF with Chinese CID font.
 pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
 c=canvas.Canvas(str(P/'reports'/f'{name}.pdf'),pagesize=(595,842));c.setTitle(name);y=794
 for line in body.splitlines():
  if not line.strip():y-=9;continue
  heading=line.startswith('#');line=line.lstrip('# ')
  for chunk in textwrap.wrap(line,width=43 if heading else 48,replace_whitespace=False):
   if y<55:c.showPage();y=794
   c.setFont('STSong-Light',14 if heading else 10);c.drawString(42,y,chunk);y-=21 if heading else 16
 if name=='光学性能报告':
  c.showPage();c.setFont('STSong-Light',14);c.drawString(42,800,'MTF 对比：曲线为计算结果，标记为原厂图人工读数')
  c.drawImage(str(P/'analysis/mtf_comparison.png'),25,540,width=545,height=182)
  c.drawImage(str(P/'analysis/lens_section.png'),25,260,width=545,height=227)
 c.save()
print(json.dumps({'per_aperture':errors,'overall':overall,'pass':passed},indent=2))
