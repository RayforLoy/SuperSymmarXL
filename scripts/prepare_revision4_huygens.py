from pathlib import Path
S=Path(__file__).parent
text=(S/'huygens_full_revision3.py').read_text().replace('revision3','revision4')
text=text.replace("R/'agent_search/higher7_asphereonly1_best.zmx'", "R/'SuperSymmarXL_150_R4_f5p6.zmx'")
(S/'huygens_full_revision4.py').write_text(text,encoding='utf-8')
