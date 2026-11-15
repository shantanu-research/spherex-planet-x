# SPHEREx Sky Flipbook

SPHEREx observes the infrared sky through a spatially varying filter. Blinking images at different wavelengths can make an unchanged source look variable. Sky Flipbook lets users inspect observation dates, wavelength coverage, masks and source files before interpreting apparent motion or changing brightness.

Users can select five project fields or resolve a name/coordinate, view individual exposures or wavelength-balanced visits, compare differences, follow catalogue proper motion, inspect native aperture measurements, and export GIF/MP4 animations. Simulations require explicit selection and are labelled throughout.

The real-data pipeline reads IMAGE, VARIANCE, FLAGS, ZODI and spectral WCS from SPHEREx FITS. It applies quality masks, registers onto a common celestial grid, balances shared wavelength bins and propagates marginal variances. Reference overlays use Gaia and CatWISE. Accessible tables, keyboard navigation, native dialogs and progress indicators support the visual interface.

The supplied collection has 42 FITS files across five fields; 41 have usable pixels in the default fields. The repository's reproducible validation report records mode availability and aperture measurements. Coverage is sparse: one target has only one visit, and many detector/visit combinations lack shared wavelengths. Those comparisons are explicitly unavailable. This software validation is not an astrophysical discovery or independent validation of the supplied catalogue coordinates.

Known scientific limits include masked bright cores, no PSF homogenization/aperture correction, unmodelled resampling covariance and calibration systematics, and tracking without annual parallax. No real-data flicker-suppression precision, molecular identification or Planet X detection is claimed.

The Docker image and Render Blueprint are prepared. Public hosting requires an authorized hosting connection and has not been verified. This description is ready for team review; an official challenge submission has not been made.

Sources: NASA SPHEREx observations from IRSA/Caltech/IPAC; team-supplied Google Drive project files; Gaia DR3; CatWISE2020; CDS Sesame. Dependencies include Astropy, NumPy, SciPy, HTTPX, Pillow and FFmpeg. AI assistance was used for code, testing and documentation. Confirm team attribution and the official competition's current requirements before submission.
