from pathlib import Path
p=Path('SuperSymmarXL/scripts/make_reports.py');s=p.read_text(encoding='utf-8')
s=s.replace("colors=['#1767a6'", "dense=json.loads((P/'analysis/dense_mtf.json').read_text()) if (P/'analysis/dense_mtf.json').exists() else None\ncolors=['#1767a6'")
s=s.replace("ls='--' if j==0 else '-';ax.plot(h,y[:,2*k+j],ls,color=colors[k],label=f'{f} lp/mm {dr}')", "ls='--' if j==0 else '-'\n   if dense:\n    dd=dense[fn][k];xx=np.array(dd['x'])*{'5.6':.68,'8':.78,'22':1}[fn]*100;yy=np.array(dd['y'])[:,j];ax.plot(xx,yy,ls,color=colors[k],label=f'{f} lp/mm {dr}')\n   else:ax.plot(h,y[:,2*k+j],ls,color=colors[k],label=f'{f} lp/mm {dr}')")
s=s.replace('完整数值见 analysis/mtf_comparison.csv，叠图见 analysis/mtf_comparison.png。','完整数值见 analysis/mtf_comparison.csv，叠图见 analysis/mtf_comparison.png。叠图曲线取自原生 512 采样的 MTF 随视场分析；定量误差使用独立固定视场复算。原生扫描覆盖 f/5.6 的 0–68%、f/8 的 0–78%、f/22 的 0–100% 像高；扫描曲线不等于所有中间点都有独立原厂对照数据。')
p.write_text(s,encoding='utf-8')
