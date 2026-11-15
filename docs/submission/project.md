# SPHEREx Sky Flipbook — submission draft

Explore infrared sky observations as aligned images, with explicit distinctions between real archive data and simulations. The project addresses SPHEREx's position-dependent wavelength coverage by checking the spectral WCS before comparing individual exposures across visits.

## Implemented and tested

Archive discovery and bounded cutout fetching; WCS image alignment; zodiacal model subtraction; flagged-pixel exclusion; explicit simulation selection; per-pixel wavelength overlap checks for longest-baseline pairs; GIF and MP4 exports; Docker and Render configuration.

## Evidence and limits

The targeted automated suite covers source provenance, input validation, archive grouping, alignment, masking, wavelength mismatch rejection, and valid MP4 encoding. A real Barnard's Star D6 FITS file from the project Drive was inspected and its spectral WCS evaluated. These checks are not five-target scientific validation. Live archive availability has been intermittent. No validated discovery, photometric precision, or measured proper-motion accuracy is claimed.

Deployment and full scientific validation remain prerequisites for final submission. The current temporal matching compares individual exposures; visit co-addition, difference processing, motion tracking, and false colour still need integration with real exposures. The original simulation implements additional demonstrations, which must be labelled as simulations.

## Sources and acknowledgement

NASA SPHEREx observations served by IRSA at Caltech/IPAC: https://irsa.ipac.caltech.edu/Missions/spherex.html
Astropy: https://www.astropy.org/
SciPy: https://scipy.org/
FFmpeg: https://ffmpeg.org/

Project planning and test FITS files were supplied by the team through Google Drive. AI assistance was used for code changes, debugging, and documentation. Team attribution and current competition submission requirements must be verified before submission.
