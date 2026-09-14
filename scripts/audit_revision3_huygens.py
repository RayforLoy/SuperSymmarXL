"""Independent native Huygens-vs-FFT audit; one app, no saved ZMX.

Initial matched runs use FFT pupil 128/256 and Huygens pupil 128/256,
image grid 256, automatic ImageDelta=0. Huygens results with unconverged
image windows are explicitly provisional; agreement is not presumed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import time
import numpy as np

P=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model',type=Path,default=P/'revision3/macro_parallel1_best.zmx')
parser.add_argument('--name',default='huygens_validation')
parser.add_argument('--image-size',type=int,default=256)
parser.add_argument('--image-delta',type=float,default=0.0,help='Micrometers, 0 is native automatic default')
parser.add_argument('--sizes',nargs='+',type=int,default=[128,256])
parser.add_argument('--cases',default='5.6:0,0.4,0.6,0.68;22:0,0.8,1')
parser.add_argument('--psf-window',action='store_true',help='Compute matching native Huygens PSF grid width and tail fractions (additional integration).')
args=parser.parse_args()
if not args.model.is_file():raise FileNotFoundError(args.model)
original_hash=hashlib.sha256(args.model.read_bytes()).hexdigest()
cases={fn:[float(x) for x in hs.split(',')] for fn,hs in (part.split(':') for part in args.cases.split(';'))}
R=P/'revision3'
exec(Path(__file__).with_name('probe_zos.py').read_text().split("print('system'")[0])
start=time.time()
report={'model':str(args.model.resolve()),'model_filename':args.model.name,'source_model_sha256':original_hash,
        'official_fft_documentation':'https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v252/en/OpticStudio_User_Guide/OpticStudio_Help/topics/FFT_MTF.html',
        'official_huygens_documentation':'https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v252/en/OpticStudio_User_Guide/OpticStudio_Help/topics/Huygens_MTF.html',
        'method':'Native FFT and Huygens analyses; identical physical apertures, image plane, six wavelengths and f-number; no ZMX saved.',
        'settings_contract':'IAS_HuygensMtf exposes PupilSampleSize, ImageSampleSize, ImageDelta (um), Field and Wavelength.',
        'warnings':['FFT may be inaccurate for extreme exit-pupil stretching in cosine space, per Ansys. Huygens still needs pupil and image-window convergence.',
                    'ImageDelta=0 is native automatic spacing. Initial image grid=256 does not by itself prove PSF/window convergence; record raw native output and sample-frequency spacing.'],
        'methods':['Native FFT MTF','Native Huygens MTF; direct diffraction integral'],
        'settings':{'pupil_sampling':args.sizes,'image_sampling':args.image_size,'image_delta':args.image_delta,'image_delta_unit':'um','six_wavelengths':True,'polarization':False},
        'results':[],'rows':[],'failures':[]}

def decode(path):
    b=path.read_bytes()
    if b[:2] in [b'\xff\xfe',b'\xfe\xff']:return b.decode('utf-16')
    for codec in ['utf-8','gb18030']:
        try:return b.decode(codec)
        except UnicodeDecodeError:pass
    return b.decode('utf-8',errors='replace')

def values(results,path):
    results.GetTextFile(str(path))
    raw=decode(path)
    warnings=[line for line in raw.splitlines() if any(s in line.lower() for s in ['warning','error','sampling too','警告','错误','采样不足'])]
    if results.NumberOfDataSeries<1:raise RuntimeError('No native MTF data series. '+raw[:500])
    d=results.GetDataSeries(0)
    xx=np.asarray(list(d.XData.Data),dtype=float)
    yy=np.asarray(list(d.YData.Data),dtype=float).reshape(d.YData.Data.GetLength(0),-1)
    if yy.shape[1]!=2 or xx[-1]<20 or len(xx)<2:raise RuntimeError('Unexpected native MTF data shape or frequency range.')
    vv=[float(np.interp(f,xx,yy[:,j])) for f in [5,10,20] for j in [0,1]]
    if not np.all(np.isfinite(vv)) or min(vv)<0 or max(vv)>1.000001:
        warnings.append('Nonfinite or out-of-range native MTF values; not accepted as reliable MTF.')
    return {'frequency_lp_mm':[5,10,20], 'values_5T_5S_10T_10S_20T_20S':vv,
            'frequency_grid_count':len(xx),'frequency_grid_min_step':float(np.min(np.diff(xx))),
            'raw_text_file':str(path),'raw_header':raw[:1600],'warnings':warnings}

def persist():
    rows=[]
    for record in report['results']:
        for size,val in record['samples'].items():
            ff=val['FFT']['values_5T_5S_10T_10S_20T_20S'];hh=val['Huygens']['values_5T_5S_10T_10S_20T_20S']
            for k,freq in enumerate([5,10,20]):
                rows.append({'aperture':record['f_number'],'height':record['reference_height_fraction'],'frequency_lp_mm':freq,
                             'FFT_T':ff[2*k],'FFT_S':ff[2*k+1],'Huygens_T':hh[2*k],'Huygens_S':hh[2*k+1],
                             'pupil_sampling':int(size),'image_sampling':args.image_size,'image_delta':args.image_delta,'image_delta_unit':'um',
                             'warnings':val['FFT']['warnings']+val['Huygens']['warnings'],'image_window_convergence_proven':False})
    report['rows']=rows
    report['seconds']=time.time()-start
    (R/(args.name+'.json')).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')

try:
    sys.LoadFile(str(args.model.resolve()),False)
    initial_plane=float(sys.LDE.GetSurfaceAt(12).Thickness)
    sd=sys.SystemData
    report['common_image_distance_mm']=initial_plane
    report['wavelengths']=[{'um':float(sd.Wavelengths.GetWavelength(i).Wavelength),'weight':float(sd.Wavelengths.GetWavelength(i).Weight)} for i in range(1,sd.Wavelengths.NumberOfWavelengths+1)]
    report['caps']=[{'surface':i,'clear_radius_mm':float(sys.LDE.GetSurfaceAt(i).SemiDiameter)} for i in [1,2,3,4,5,6,8,9,10,11,12]]
    fields=sd.Fields
    all_heights=sorted({0.0,1.0}|{h for hs in cases.values() for h in hs})
    while fields.NumberOfFields>1:fields.RemoveField(fields.NumberOfFields)
    fields.SetFieldType(Z.SystemData.FieldType.Angle)
    for h in all_heights[1:]:fields.AddField(0,52.5 if h==1 else math.degrees(math.atan(193*h/148.1)),1)
    assert fields.NumberOfFields<=12 and fields.GetField(fields.NumberOfFields).Y==52.5
    fft=sys.Analyses.New_FftMtf();huy=sys.Analyses.New_HuygensMtf()
    fs=Z.Analysis.Settings.Mtf.IAS_FftMtf(fft.GetSettings())
    hs=Z.Analysis.Settings.Mtf.IAS_HuygensMtf(huy.GetSettings())
    fs.MaximumFrequency=20;hs.MaximumFrequency=20
    fs.Wavelength.UseAllWavelengths();hs.Wavelength.UseAllWavelengths()
    fs.UsePolarization=False;hs.UsePolarization=False
    hs.ImageSampleSize=getattr(Z.Analysis.SampleSizes,f'S_{args.image_size}x{args.image_size}')
    hs.ImageDelta=args.image_delta
    report['image_sample_size']=args.image_size
    report['requested_image_delta_um']=args.image_delta
    for fn,heights in cases.items():
        sd.Aperture.ApertureValue=148.1/float(fn)
        for h in heights:
            field_no=all_heights.index(h)+1
            fs.Field.SetFieldNumber(field_no);hs.Field.SetFieldNumber(field_no)
            record={'f_number':fn,'reference_height_fraction':h,'angle_deg':float(fields.GetField(field_no).Y),'samples':{}}
            report['results'].append(record)
            for size in args.sizes:
                try:
                    print('start independent MTF',fn,h,'pupil',size,'image',args.image_size,'delta',args.image_delta,flush=True)
                    fs.SampleSize=getattr(Z.Analysis.SampleSizes,f'S_{size}x{size}')
                    hs.PupilSampleSize=getattr(Z.Analysis.SampleSizes,f'S_{size}x{size}')
                    fft.ApplyAndWaitForCompletion()
                    tag=f'{args.name}_f{fn}_h{h}_p{size}'.replace('.','p')
                    fval=values(fft.GetResults(),R/(tag+'_FFT.txt'))
                    huy.ApplyAndWaitForCompletion()
                    hval=values(huy.GetResults(),R/(tag+'_Huygens.txt'))
                    delta=np.asarray(hval['values_5T_5S_10T_10S_20T_20S'])-np.asarray(fval['values_5T_5S_10T_10S_20T_20S'])
                    record['samples'][str(size)]={'FFT':fval,'Huygens':hval,'Huygens_minus_FFT':delta.tolist(),'maximum_absolute_difference':float(max(abs(delta)))}
                    if args.psf_window:
                        psf=sys.Analyses.New_HuygensPsf()
                        try:
                            ps=Z.Analysis.Settings.Psf.IAS_HuygensPsf(psf.GetSettings())
                            ps.PupilSampleSize=getattr(Z.Analysis.SampleSizes,f'S_{size}x{size}')
                            ps.ImageSampleSize=getattr(Z.Analysis.SampleSizes,f'S_{args.image_size}x{args.image_size}')
                            ps.ImageDelta=args.image_delta;ps.Field.SetFieldNumber(field_no);ps.Wavelength.UseAllWavelengths()
                            ps.UsePolarization=False
                            psf.ApplyAndWaitForCompletion();pr=psf.GetResults()
                            pr.GetTextFile(str(R/(tag+'_HuygensPSF.txt')))
                            if pr.NumberOfDataGrids<1:raise RuntimeError('No native PSF data grid.')
                            gd=pr.GetDataGrid(0)
                            # Huygens PSF DataGrid axes use micrometers, unlike
                            # chief-ray/centroid coordinates in the text header (mm).
                            mat=np.array(list(gd.ValueData.Data),dtype=float).reshape(gd.ValueData.Data.GetLength(0),-1)
                            total=float(mat.sum());border=np.zeros(mat.shape,dtype=bool)
                            strip=max(1,int(min(mat.shape)*.05))
                            border[:strip,:]=True;border[-strip:,:]=True;border[:,:strip]=True;border[:,-strip:]=True
                            core=mat[mat.shape[0]//4:3*mat.shape[0]//4,mat.shape[1]//4:3*mat.shape[1]//4]
                            record['samples'][str(size)]['HuygensPSF_window']={'Nx':int(gd.Nx),'Ny':int(gd.Ny),'native_grid_unit':'um','Dx_um':float(gd.Dx),'Dy_um':float(gd.Dy),'Dx_mm':float(gd.Dx)/1000,'Dy_mm':float(gd.Dy)/1000,'width_x_mm':float(gd.Dx*gd.Nx)/1000,'width_y_mm':float(gd.Dy*gd.Ny)/1000,'outer_5pct_border_flux_fraction':float(mat[border].sum()/total) if total else None,'central_half_width_flux_fraction':float(core.sum()/total) if total else None,'warning':'Finite grid flux fractions cannot determine missing energy outside the grid; compare wider windows.'}
                        finally:psf.Close()
                    print('Huygens-vs-FFT',fn,h,size,'max diff',round(float(max(abs(delta))),5),flush=True)
                except Exception as exc:
                    report['failures'].append({'f_number':fn,'height':h,'size':size,'error':repr(exc)})
                    print('independent MTF failure',repr(exc),flush=True)
                finally:persist()
            if '128' in record['samples'] and '256' in record['samples']:
                for algorithm in ['FFT','Huygens']:
                    a=np.array(record['samples']['128'][algorithm]['values_5T_5S_10T_10S_20T_20S'])
                    b=np.array(record['samples']['256'][algorithm]['values_5T_5S_10T_10S_20T_20S'])
                    record[algorithm+'_max_change_128_to_256']=float(max(abs(b-a)))
            persist()
    assert float(sys.LDE.GetSurfaceAt(12).Thickness)==initial_plane
    assert fields.GetField(fields.NumberOfFields).Y==52.5
    report['source_model_unchanged']=hashlib.sha256(args.model.read_bytes()).hexdigest()==original_hash
    report['full_field_deg']=105.0
    report['status']='Native results obtained; image-window convergence remains a separate requirement.' if not report['failures'] else 'Partial or failed native audit; inspect failures and raw text.'
    persist()
finally:
    app.CloseApplication()
