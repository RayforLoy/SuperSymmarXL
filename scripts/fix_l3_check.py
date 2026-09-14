from pathlib import Path
p=Path('SuperSymmarXL/scripts/l3_aperture_check.py');s=p.read_text().replace("for yy in [154.4,193]:", "a=sys.Analyses.New_FftMtf();sett=Z.Analysis.Settings.Mtf.IAS_FftMtf(a.GetSettings());sett.MaximumFrequency=20;sett.SampleSize=Z.Analysis.SampleSizes.S_128x128\nfor yy in [154.4,193]:").replace('[13.5,14,14.5,15]','[14.9,15.2,15.5,16]');p.write_text(s)
