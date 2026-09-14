from pathlib import Path
import pymupdf
p=Path('SuperSymmarXL')
d=pymupdf.open(p/'super-symmar_xl_56_150.pdf')
pg=d[1]
pg.get_pixmap(matrix=pymupdf.Matrix(3,3),clip=pymupdf.Rect(75,120,545,300)).save(p/'reference'/'mtf_infinity_detail.png')
