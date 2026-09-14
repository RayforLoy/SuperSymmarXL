"""Separate four-app search from the R2 seed, fitting within clear aperture."""
from pathlib import Path
S=Path(__file__).parent
text=(S/'agent_r4_a6_search.py').read_text()
text=text.replace("/'revision3'/'agent_search'/'higher7_asphereonly1_best.zmx'", "/'revision2'/'SuperSymmarXL_150_R2_f5p6.zmx'")
text=text.replace("/'agent_search'", "/'root_search'")
text=text.replace('15.8','15.5')
text=text.replace("default='a6_smooth1'", "default='a6_r2seed'")
text=text.replace("default=5)", "default=15)")
(S/'root_r4_a6_search.py').write_text(text,encoding='utf-8')
