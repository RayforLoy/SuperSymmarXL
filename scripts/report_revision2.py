from pathlib import Path
import json,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from xml.sax.saxutils import escape
P=Path(__file__).resolve().parents[1];R=P/'revision2'
v=json.loads((R/'validated.json').read_text());t=json.loads((P/'analysis/target_manual.json').read_text());dc=json.loads((R/'drawing_constraints.json').read_text());curves=json.loads((R/'field_curves.json').read_text())
sur=v['surfaces'];coef=v['asphere_A4_to_A12'];z=np.cumsum([0]+[s['thickness_mm'] for s in sur[:-1]])
def sag(i,r):
 rad=sur[i-1]['radius_mm'];r=np.asarray(r);out=r*r/(rad*(1+np.sqrt(1-(r/rad)**2))) if np.isfinite(rad) else np.zeros_like(r)
 if i==10:out=out+sum(a*r**p for a,p in zip(coef,[4,6,8,10,12]))
 return out
geometry=[]
for i in [2,4,10]:
 radius=min(sur[i-1]['clear_radius_mm'],sur[i]['clear_radius_mm'])
 if i==10:radius=sur[i-1]['clear_radius_mm']+.3 # conservative extension of last front sphere through possible bevel zone
 rr=np.linspace(0,radius,10001);gap=sur[i-1]['thickness_mm']+sag(i+1,rr)-sag(i,rr)
 geometry.append({'after_surface':i,'checked_radius_mm':radius,'min_gap_mm':float(min(gap)),'at_radius_mm':float(rr[np.argmin(gap)])})
assert min(g['min_gap_mm'] for g in geometry)>.25,geometry
(R/'geometry_verified.json').write_text(json.dumps(geometry,indent=2))
fig,axs=plt.subplots(1,2,figsize=(13,6),gridspec_kw={'width_ratios':[1.6,1]})
for ax in axs:
 for i,su in enumerate(sur[:-1]):
  if not su['glass']:continue
  rf=su['clear_radius_mm'];rb=sur[i+1]['clear_radius_mm'];yf=np.linspace(-rf,rf,401);yb=np.linspace(rb,-rb,401)
  verts=np.c_[np.r_[z[i]+sag(i+1,yf),z[i+1]+sag(i+2,yb)],np.r_[yf,yb]]
  ax.add_patch(Polygon(verts,fc='#d4eaf7',ec='#233c4d',lw=1.1))
 ax.axhline(0,color='gray',lw=.6);ax.axvline(z[6],color='#b25a20',ls='--',lw=1);ax.set_aspect('equal');ax.set(xlabel='Axial distance (mm)',ylabel='Radius (mm)');ax.grid(alpha=.12)
axs[0].set(xlim=(-4,82),ylim=(-44,44),title='R2: fixed clear apertures, full 105-degree field')
axs[1].set(xlim=(51,80),ylim=(-20,20),title='Rear groups: no surface intersection')
fig.suptitle('Optical sections; straight edge connections are schematic, not a mechanical production drawing')
fig.tight_layout();fig.savefig(R/'section_verified.png',dpi=180);plt.close(fig)
metrics={};all_delta=[]
fig,axs=plt.subplots(1,3,figsize=(15,5),sharey=True);cols=['#2166ac','#d56b20','#218d6d']
for ax,fn in zip(axs,['5.6','8','22']):
 yy=np.array(v['results'][fn][:len(t['data'][fn])]);ref=np.array(t['data'][fn]);delta=yy-ref;short=np.maximum(-delta,0);idx=np.unravel_index(np.argmax(short),short.shape)
 metrics[fn]={'rmse':float(np.sqrt(np.mean(delta**2))),'max_shortfall':float(short.max()),'max_absolute_error':float(abs(delta).max()),'within_3_percentage_point_lower_bound':int((delta>=-.03).sum()),'points':int(delta.size),'worst_shortfall_height_fraction':t['heights'][idx[0]],'worst_frequency_lp_mm':[5,10,20][idx[1]//2],'worst_direction':['T','S'][idx[1]%2]};all_delta.extend(delta.ravel())
 for k,f in enumerate([5,10,20]):
  for j,dr in enumerate(['T','S']):
   line=np.array(curves['results'][fn])[:,2*k+j];ax.plot(np.array(curves['heights'])*100,line,'--' if j==0 else '-',color=cols[k],label=f'{f} lp/mm {dr}')
   hh=np.array(t['heights'][:len(ref)])*100
   if j==0:ax.scatter(hh,ref[:,2*k+j],marker='x',s=28,c=cols[k])
   else:ax.scatter(hh,ref[:,2*k+j],facecolors='none',edgecolors=cols[k],s=28)
 if fn!='22':ax.axvspan(68 if fn=='5.6' else 78,100,color='gray',alpha=.09)
 ax.set(xlim=(0,100),ylim=(0,1),xlabel='Reference image height / 193 mm (%)',title=f'f/{fn}: maximum shortfall {100*short.max():.1f} pp');ax.grid(alpha=.2)
axs[0].set_ylabel('MTF');axs[2].legend(ncol=2,fontsize=8);fig.suptitle('R2 full-field MTF: model curves; manufacturer reference markers. Grey: no published reference curve.')
fig.tight_layout();fig.savefig(R/'MTF_full_field.png',dpi=180);plt.close(fig)
summary={'per_aperture':metrics,'full_field_deg':v['full_field_deg'],'min_air_gap_mm':min(g['min_gap_mm'] for g in geometry),'all_points_at_or_above_reference':all(x>=0 for x in all_delta),'all_points_within_readout_tolerance':all(x>=-.03 for x in all_delta)}
(R/'acceptance.json').write_text(json.dumps(summary,indent=2))
# Report authoring. Chinese line breaking and automatic pagination.
pdfmetrics.registerFont(TTFont('SXL',r'C:\Windows\Fonts\simhei.ttf'))
styles={
 'title':ParagraphStyle('title',fontName='SXL',fontSize=19,leading=26,spaceAfter=14,textColor=colors.HexColor('#17384b')),
 'h':ParagraphStyle('h',fontName='SXL',fontSize=13,leading=19,spaceBefore=12,spaceAfter=6,keepWithNext=True,textColor=colors.HexColor('#17384b')),
 'body':ParagraphStyle('body',fontName='SXL',fontSize=10,leading=16,spaceAfter=7,wordWrap='CJK'),
 'small':ParagraphStyle('small',fontName='SXL',fontSize=8,leading=12,wordWrap='CJK')}
def par(txt,style='body'):return Paragraph(escape(txt),styles[style])
def table(rows,widths=None):
 data=[[par(str(x),'small') for x in row] for row in rows];tb=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT');tb.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7f0f6')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#b8c7d0')),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));return tb
def footer(c,d):
 c.setFont('SXL',8);c.setFillColor(colors.gray);c.drawString(40,26,'Super-Symmar XL 150 mm | R2 reverse candidate');c.drawRightString(555,26,str(d.page))
def emit(name,story,md):
 SimpleDocTemplate(str(R/name),pagesize=(595,842),leftMargin=40,rightMargin=40,topMargin=38,bottomMargin=42).build(story,onFirstPage=footer,onLaterPages=footer)
 (R/name.replace('.pdf','.md')).write_text(md,encoding='utf-8')
fo=v['first_order'];gap=summary['min_air_gap_mm']
status='已修正最大视场及表面相交问题；MTF 尚未在所有对照点达到或超过原厂曲线。' if not summary['all_points_within_readout_tolerance'] else '已修正最大视场及表面相交问题；所取样点在读图误差范围内达到原厂 MTF 下限。'
body=[('本轮结论',status),('结构图提供的证据',f"以手册第 1 页的结构图轴上面顶点与专利第一实施例作共同定标，得到约 {dc['scale_pixels_per_mm']:.3f} 像素/mm，轴上位置残差 RMS 约 {dc['axial_residual_rms_mm']:.3f} mm。这表明它与该处方的光学结构相符，比上一版自动扩展出的外形更有依据。但它没有生产尺寸、公差和机械接口，不能据此认定为实物测量图或完整加工图。口径是读图估计，本轮按约 ±0.3 mm 的读数不确定度对待。"),('最大视场与像高',f"全部 f/5.6、f/8、f/22 文件均采用 Angle 视场，最大半视场角 {max(v['field_angles_deg']):.4f}°，全视场 {v['full_field_deg']:.1f}°。按原厂 148.1 mm 焦距，105° 全视场对应约 386.0 mm 像圈。原厂 MTF 图采用最大像高 193 mm；第 1 页照度图中的 193.9 mm 属于另一项图表标注。本轮不再把全开 MTF 曲线终点误当作系统最大视场。"),('通光口径和光阑',"各面同时设置明确的圆形通光口径、固定半口径及机械显示半口径。光阑保留自动半口径解算，随系统入瞳直径和 f 数变化；不再固定在上一版某一光圈的数值。后组相关面号为：10 面胶合组后非球面，11 面末片前表面，12 面末片后表面。面号含独立光阑面。"),('一阶参数约束',f"模型主波长有效焦距 {fo['EFFL']:.5f} mm（原厂 148.1 mm）；入瞳位置 {fo['ENPP']:.5f} mm（原厂 36.6 mm）；模型首面到末面轴向长度 {sum(s['thickness_mm'] for s in sur[:-1]):.5f} mm（原厂约 77.4 mm）。曲率只在小范围内调整，中心厚度和空气间隔以专利与结构图为基础保留。"),('理想 MTF 与原厂曲线的关系',"本轮把原厂 MTF 作为性能下限，优于原厂的计算结果不因“不贴合曲线”受到主要惩罚。但理想模拟并不逻辑上保证优于另一条原厂曲线：当前原厂数据表没有明确说明图线是实测、典型值还是设计计算，也没有完整公开原始处方和非球面。能否达到下限必须以相同光谱、光圈、视场和聚焦条件下的复算结果判断。"),('MTF 复算条件',"采用原厂六波长 546、644、588、480、436、405 nm 和权重 24.6、18.6、22.1、12.4、15.2、7.1%，无限远物距、平面像面和真实光线瞄准。主定量数据采用 f/5.6 的 1024 采样及 f/8、f/22 的 512 采样，并与 256 采样比较。图中曲线采用独立的 21 个完整视场样点、512 采样；原厂标记为扫描图人工读数。读图误差约 2-4 个百分点，不能把最后一位小数当作原厂精度。RMSE 同时统计高于和低于原厂的差异；本轮主要使用最大低于原厂幅度与达到下限的样点数判定，不把超额性能当作主要缺陷。"),('尚未完成的等效验证',"统一像面仍是优化变量，没有严格强制原厂说明的“f/5.6 轴上 20 lp/mm 达到最大”的完整聚焦程序。有限倍率、透射率、照度、完整机械遮挡与量产公差尚未完成等效验证。理想 MTF 未达标的视场需继续改善处方，不能归因于制造误差。")]
story=[par('光学性能报告 - R2 修订','title')];md='# 光学性能报告 - R2 修订\n\n'
for title,txt in body[:5]:story.extend([par(title,'h'),par(txt)]);md+=f'## {title}\n\n{txt}\n\n'
story.append(table([['面号','通光半径 mm','作用']]+[[i,sur[i-1]['clear_radius_mm'],{5:'第三片前表面',6:'第三片后表面',8:'胶合组前表面',9:'胶合面',10:'非球面',11:'末片前表面',12:'末片后表面'}[i]] for i in [5,6,8,9,10,11,12]],[60,130,315]))
for title,txt in body[5:7]:story.extend([par(title,'h'),par(txt)]);md+=f'## {title}\n\n{txt}\n\n'
rows=[['光圈','RMSE / 百分点','最大低于原厂 / 百分点','低于原厂不超过 3 点的样点']]
for fn,m in metrics.items():rows.append([fn,f"{100*m['rmse']:.2f}",f"{100*m['max_shortfall']:.2f}",f"{m['within_3_percentage_point_lower_bound']} / {m['points']}"]);md+=f"- f/{fn}: RMSE {100*m['rmse']:.2f} 点；最大低于原厂 {100*m['max_shortfall']:.2f} 点。\n"
story.append(table(rows,[55,120,145,185]));story.extend([par(body[7][0],'h'),par(body[7][1])]);md+='\n'+body[7][1]+'\n'
story.extend([PageBreak(),par('完整视场 MTF 与结构复核','h'),Image(str(R/'MTF_full_field.png'),width=515,height=172),Spacer(1,10),Image(str(R/'section_verified.png'),width=515,height=238),par(f'结构验证：保守延伸最后一片前球面至胶合组后表面半径并加 0.3 mm 读图余量，最小空气间隙 {gap:.4f} mm，无表面相交。边缘连线是示意，不能代替倒角加工图。','small'),Image(str(R/'reference_section.png'),width=240,height=197)])
emit('光学性能报告_R2.pdf',story,md)
pbody=[('结论',f"本轮已消除光学表面交叠，在名义几何上可继续进行样机设计评估。最小保守空气间隙约 {gap:.4f} mm。该数字是处方几何检查结果，不是已经完成公差分配后的最小保证装配间隙。MTF 状态：{status}"),('上一版问题如何修正',"上一版把 Zemax 自动扩大的半口径当成可用镜片外形，导致后两片在大半径处相交。本轮用手册结构图约束各面通光区域，并检查最后一片前球面的保守延伸区域。未通过移动像面、改变显示缩放或仅隐藏边缘来消除重叠；明确的表面口径也参与光线追迹和 MTF 计算。"),('非球面与边缘加工',"胶合组后外表面仍为偶次非球面，最终系数和面号保存在 ZMX 与 prescription.csv/validated.json。结构图中的边缘斜线提示应存在外形收边或倒角，但其尺寸及工艺未公开。下一步必须把有效口径、外径、倒边、压圈和胶层分别定义，不能把本报告连接光学面端点的示意线直接发给工厂加工。"),('材料与供应',"使用 SCHOTT 目录的 KF9、N-LAK33B、N-SK5、F2、K10 作为全色散玻璃候选。历史目录可用于复算，但不代表现货可采购；应取得实际熔次折射率、均匀性及毛坯尺寸。材料替换需要重新优化整个 405-644 nm 光谱，不能只匹配 nd 和 vd。"),('制造放行前必须完成的工作',"先关闭未达到原厂下限的 MTF 差距，并确认原厂聚焦和测量条件；然后冻结有效口径与完整机械尺寸链、非球面检测方案和玻璃熔次数据。需要开展偏心、倾斜、曲率、厚度、间距、非球面面形、胶层和温度误差的公差分析，以及有装配补偿的 Monte Carlo 与实物 MTF 验证。本轮没有完成这些工作，因此不提供生产良率、成本或交期承诺。"),('本轮可确认与不能确认的事项',"可确认：完整 105° 视场设置、明确参与追迹的各面通光口径、受检区域正空气间隙，以及由该 ZMX 产生的 MTF 数值。不能确认：结构图与每一支实物的机械尺寸完全一致、理想 MTF 已全面优于原厂、或者这份候选已经适合直接批量投产。")]
story=[par('生产可能性报告 - R2 修订','title')];md='# 生产可能性报告 - R2 修订\n\n'
for title,txt in pbody:story.extend([par(title,'h'),par(txt)]);md+=f'## {title}\n\n{txt}\n\n'
story.extend([par('相邻组空气间隙检查','h'),table([['空气位于面后','检查半径 mm','最小间隙 mm']]+[[g['after_surface'],f"{g['checked_radius_mm']:.3f}",f"{g['min_gap_mm']:.4f}"] for g in geometry],[130,170,205]),Image(str(R/'section_verified.png'),width=515,height=238)])
emit('生产可能性报告_R2.pdf',story,md)
print(json.dumps(summary,indent=2))
