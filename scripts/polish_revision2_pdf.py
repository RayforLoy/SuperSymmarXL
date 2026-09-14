from pathlib import Path
p=Path('SuperSymmarXL/scripts/report_revision2.py');s=p.read_text(encoding='utf-8').replace('from reportlab.pdfbase.cidfonts import UnicodeCIDFont','from reportlab.pdfbase.ttfonts import TTFont').replace("pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))","pdfmetrics.registerFont(TTFont('SXL',r'C:\Windows\Fonts\simhei.ttf'))").replace("'STSong-Light'","'SXL'").replace("spaceBefore=12,spaceAfter=6,textColor", "spaceBefore=12,spaceAfter=6,keepWithNext=True,textColor")
p.write_text(s,encoding='utf-8')
