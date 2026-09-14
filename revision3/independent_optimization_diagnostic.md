# Independent static diagnosis of R3 optimization

This diagnosis reads `macro_parallel1_result.json`, its saved ZMX, the current optimization script and the local SCHOTT snapshot. It does not run Zemax or change an optical model.

The macro candidate was evaluated at FFT sampling 128. Its reported maximum manufacturer deficit is 0.130917 and its minimum checked rear air gap is 0.593952 mm. These are an intermediate result, not final acceptance.

## Why f/22 axis MTF is low

The common image distance is 135.027758 mm, whereas primary-wavelength paraxial BFL is 135.904142 mm. Thus the f/5.6 axis-20 maximum is 0.876384 mm in front of the primary paraxial focus. At f/22 the central pupil samples much smaller ray heights and tends toward the paraxial focus. Keeping the full-aperture optimum fixed can therefore leave the stopped-down axis defocused.

The intermediate axis 20 lp/mm values are 0.533182 at f/5.6, 0.683464 at f/8 and 0.551911 at f/22, versus dense manufacturer readings 0.64, 0.69 and 0.67. This pattern is consistent with appreciable longitudinal spherical aberration/focus shift: f/8 is much better than both the larger and smaller pupils. It is not evidence that the manufacturer focusing rule should be relaxed.

A first-order defocus estimate gives pupil-edge OPD about 0.415 waves at 546 nm for a 0.876 mm axial displacement at f/22, using `abs(delta)/(8*N^2*lambda)`. This is only a paraxial estimate; it excludes actual wavelength-dependent aberrations and is not a substitute for native MTF.

## Chromatic constraint currently omitted from the explicit first-order residual

Independent paraxial matrix propagation with the saved radii/thicknesses and the local Sellmeier records reproduces primary BFL 135.904142 mm. The six calculated paraxial BFL values are:

| Wavelength um | Paraxial BFL mm |
|---|---:|
|0.546|135.904142|
|0.644|136.360550|
|0.588|136.099103|
|0.480|135.643702|
|0.436|135.588429|
|0.405|135.713585|

The six-wave BFL span is 0.772120 mm, compared with 0.698061 mm for R2 and 0.695813 mm for the original spherical patent seed. The manufacturer-weighted centroid is 135.938308 mm and spectral RMS spread around it is 0.268547 mm. The weighted RMS displacement from the current common image plane is 0.949325 mm. These are paraxial spectral descriptors, not real-ray focus positions or process tolerances.

## One executable improvement

Retain the manufacturer's axis-20 focusing rule and the existing close-focus regularizer. Add a cheap explicit chromatic-spread residual to condition the radius/thickness search: cache `INDX` for all six wavelengths once per worker, propagate the existing paraxial matrix for each wavelength, form `BFL(lambda)-weighted_mean_BFL`, and append weight-scaled spectral residuals to the optical objective. Use a soft target for manufacturer-weighted spectral RMS around 0.20-0.25 mm rather than a hard zero-achromatism requirement. Continue optimizing the actual full-aperture MTF; the added residual only helps the search avoid trading corrected off-axis curves for worse stopped-down chromatic axis blur. It adds matrix arithmetic, not new FFT analyses or Zemax instances.

The geometric knob set most directly associated with this residual is the cemented pair's front, cemented and back curvatures S8/S9/S10 together with its two center thicknesses. Those variables also influence spherical aberration and field curvature, so they should be optimized jointly with S10 A4 rather than independently hand-adjusted. Higher-order S10 coefficients remain available to restore off-axis behavior after reducing the low-order focus shift. This proposal has not been numerically tested and is not a guarantee that the current six-element/material constraints can exceed every manufacturer curve.

## FFT derivative noise and pupil clipping

The worker identical-input test verifies determinism across native instances. It does not establish differentiability. Circular apertures clip individual sampled pupil rays; as a curvature or spacing changes, a ray can move across an aperture boundary, producing a discrete change in the FFT pupil mask. This can contaminate forward-difference derivatives even though repeated evaluations are identical. Scalar maximization over an axis MTF magnitude can also switch between focus branches and further roughen the outer objective.

The macro candidate's f/5.6 20T changes from approximately 0.500 at h=.5 to 0.035 at h=.6. This is a reason to inspect its pupil maps; it is not by itself proof of a numerical error, since real aberrations and MTF zeros can also cause a steep change. The existing grid-pupil audit will distinguish clipping from an unvignetted pupil, but geometric pupil fraction alone cannot reproduce radiometric illumination.

If the explicit chromatic step stalls at `xtol`, a bounded numerical check is useful before changing the physical aperture: evaluate the same candidate at 256/512 and compare central finite differences at parameter steps h=.02 and .04. Large derivative sign changes with sampling or step would justify a coarser central-difference/trust-region search. Do not improve normalized MTF by shrinking fixed clear apertures; that would change the intended lens and its illumination.

## Other static observations

When axis-focus enforcement is enabled, x[27] is overwritten by the internal focus solve and is therefore an inactive optical degree of freedom apart from regularization. Removing it from that mode would avoid one redundant Jacobian column. This is a minor efficiency improvement, not an optical correction.

Focus optimization currently uses a local Brent bracket and falls back to bounded scalar minimization. A coarse deterministic axial scan followed by local bounded refinement around the best scanned peak would be a stronger final audit of the global axis-20 maximum, especially if a redesigned candidate changes spherical-aberration branches.

Final acceptance still requires native high-sampling MTF, actual image-height registration, fixed clear-aperture geometry and common-focus verification. No static matrix result above replaces those checks.
