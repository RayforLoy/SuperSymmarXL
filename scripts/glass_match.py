from pathlib import Path
import numpy as np
p=Path(r'C:\Users\liuru\Documents\Zemax\Glasscat\SCHOTT.AGF')
g=[]
for line in p.read_text(errors='ignore').splitlines():
 s=line.split()
 if not s: continue
 if s[0]=='NM': cur={'name':s[1],'formula':int(float(s[2])),'nd':float(s[4]),'vd':float(s[5])};g.append(cur)
 if s[0]=='CD':cur['c']=list(map(float,s[1:]))
def n(a,w):
 c=a['c']; l=w*w
 if a['formula']==2:return np.sqrt(1+sum(c[i]*l/(l-c[i+1]) for i in [0,2,4]))
 if a['formula']==1:return np.sqrt(c[0]+c[1]*l+sum(c[i]*l**(-(i-1)) for i in range(2,6)))
 return 0
for ne,ve in [(1.52583,51.25),(1.75844,52.09),(1.59142,61.03),(1.62408,36.12),(1.50349,56.13)]:
 for a in g:
  try:a['ne']=n(a,.546074);a['ve']=(a['ne']-1)/(n(a,.479991)-n(a,.643847));a['err']=abs(a['ne']-ne)*100+abs(a['ve']-ve)
  except: a['err']=1e6
 print(ne,ve,[(a['name'],round(a['ne'],6),round(a['ve'],3)) for a in sorted(g,key=lambda a:a['err'])[:4]])

