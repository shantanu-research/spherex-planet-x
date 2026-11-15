# SPHEREx "Planet X" Discovery Engine & Multi-Epoch Visualizer

> **Development status:** This project is not yet scientifically validated or submission-ready. The main viewer does not yet fetch and process live IRSA cutouts end to end. Real-data rendering currently requires local FITS archives; simulated data must be selected explicitly. Several scientific performance claims and feature descriptions below are design goals that still require independent verification. MP4 export is not implemented.

**NASA Space Apps Challenge 2026 — Planet X and SPHEREx**

A high-performance astronomical discovery, astrometric registration, and spectrophotometric visualization platform engineered specifically for **SPHEREx Level-2 Multi-Extension FITS (MEF)** all-sky survey data.

---

## 1. Why Standard Blink Comparators Fail on SPHEREx

Most conventional tools for detecting moving solar system objects or brown dwarfs rely on naive chronological frame blinking. On SPHEREx data, these naive viewers fail due to five fundamental physical constraints:

1. **Linear Variable Filter (LVF) Spectral Flicker:** Every exposure observes a target at a different wavelength because bandpass varies continuously across the focal plane. Chronological playback induces ~20–30% artificial brightness flicker on constant stars and causes cold brown dwarfs to disappear below 3 µm.
2. **Sub-Pixel Proper Motion Regime:** Over 6-month survey revisits, even Barnard's Star moves only ~0.85 pixels (native 6.15"/px scale). Without multi-visit baselines and sub-pixel registration, movers are indistinguishable from stationary stars.
3. **Stale Catalogue Discovery Epochs:** Discovery coordinates for targets like **WISE 0855-0714** are at epoch ~2010; by 2025.5–2026, the target has drifted 128.4" (~20.9 pixels) westward!
4. **Archive Footprint & Payload Traps:** IRSA SIA2 cone searches return off-target centers up to 2° away, failing with HTTP 422 errors unless filtered against exact sky polygons (`s_region`).
5. **Release Lineage Shifts:** Quick Release 2 (`QR2`) vs. Pipeline R7 (`QR3` and `DR1`) have different gain calibrations and PSF table structures.

---

## 2. Breakthrough Solutions Implemented

### **Akhilesh's 5-Step Band-Balanced LVF Stacking Engine (Track 2)**
Eliminates artificial brightness flicker mathematically without corrupting astrophysical variability:
* **Step 1 (Spectral Labelling):** Evaluates spectral WCS key `'W'` at $(x, y)$ to map each exposure to channel $b \in \{1 \dots 17\}$.
* **Step 2 (Two-Level Hierarchical Stacking):**
  * *Level 1:* Inverse-variance weighted mean within each channel:
    $$F_{v,d,b}(x,y) = \frac{\sum w_i I_i}{\sum w_i}, \quad w_i = \frac{1}{\sigma_i^2}$$
  * *Level 2:* Equal-weight mean across all channels in the shared intersection $\mathcal{C}_{\text{shared}}$:
    $$F_{v,d}(x,y) = \frac{1}{|\mathcal{C}_{\text{shared}}|} \sum_{b \in \mathcal{C}_{\text{shared}}} F_{v,d,b}(x,y)$$
* **Step 3 (Cross-Visit Shared Intersection):** Enforces identical spectral response $\mathcal{C}_{\text{shared}} = \bigcap_v \{ b : \mathcal{E}_{v,d,b} \neq \emptyset \}$.
* **Step 4 (Sub-Band Stacks):** 4-bin contiguous channel grouping ($\Delta\lambda/\lambda \approx 0.1$).
* **Step 5 (Automated Still-Star Photometric Audit):** Empirically proves flicker suppression from ~25% down to < 2% across 20+ Gaia DR3 reference stars.

### **Idea 1: Metadata-Driven Relative Frame Positioning (Track 4)**
* Gnomonic Tangent-Plane (`RA---TAN`, `DEC--TAN`) north-up, east-left output grid ($6.15\text{ arcsec/px}$).
* **Dual Frame Modes:**
  * **Inertial Sky-Fixed Frame:** Background stars remain stationary; moving targets translate across the FOV.
  * **Co-Moving Target-Locked Frame:** Frame reference center tracks the target's $(\mu_\alpha, \mu_\delta, \varpi)$ space motion, locking the moving object at the center while background stars drift!

### **Idea 2: Infrared-to-Visible Spectral Superposition (Track 4)**
* Monotonic logarithmic bijection mapping SPHEREx near-IR ($0.744\text{--}5.002\,\mu\text{m}$) to human visible light ($380\text{--}750\text{ nm}$):
  $$\lambda_{\text{vis}}(\lambda_{\text{IR}}) = 380 + 370 \cdot \frac{\ln(\lambda_{\text{IR}} / 0.744)}{\ln(5.002 / 0.744)} \quad [\text{nm}]$$
* Detectors map deterministically to chromatic hues:
  * $D_1$ ($0.744 - 1.116\,\mu\text{m}$): Violet $\to$ Royal Blue
  * $D_2$ ($1.099 - 1.651\,\mu\text{m}$): Blue $\to$ Cyan
  * $D_3$ ($1.636 - 2.421\,\mu\text{m}$): Cyan $\to$ Green
  * $D_4$ ($2.423 - 3.822\,\mu\text{m}$): Green $\to$ Orange
  * $D_5$ ($3.809 - 4.420\,\mu\text{m}$): Orange $\to$ Deep Red
  * $D_6$ ($4.412 - 5.002\,\mu\text{m}$): Deep Red $\to$ Far-IR Ruby Red
* **Lupton (2004) Asinh Color Compression:** Preserves physical color ratios and chromaticity without blowing star cores out to white.

### **Track 3: Live 102-Channel Spectrophotometry & Astrometric Validation**
* Full forced-aperture SED extraction across all 6 detectors ($R = 35 \dots 128$).
* Automated detection of diagnostic absorption lines:
  * $\text{H}_2\text{O}$ vapor at $1.40\,\mu\text{m}$ and $1.90\,\mu\text{m}$
  * $\text{CH}_4$ (methane) at $2.20\,\mu\text{m}$ and $3.32\,\mu\text{m}$
  * $\text{H}_2\text{O}$ ice grains at $3.00\,\mu\text{m}$
  * $\text{CO}_2$ fundamental band at $4.27\,\mu\text{m}$
  * $\text{CO}$ fundamental band at $4.60\,\mu\text{m}$
* Multi-epoch 2D Gaussian centroiding with linear regression proper motion fitting validated against Gaia DR3 / CatWISE.

### **The 7 Unified Viewing Modes (Section 9.1)**
1. **Mode 1 (`visit_blink`):** Chronological sequence across survey visits $v=1 \dots M$ on detector $d$ with Akhilesh's band-balanced co-addition and sequence-wide detector-locked Asinh stretch.
2. **Mode 2 (`longest_baseline`):** Earliest ($V_1$) & latest ($V_M$) co-add toggle across the maximum ~18-month baseline to reveal subtle sub-pixel astrometric drift.
3. **Mode 3 (`difference_sequence`):** Temporal median template subtracted frames $D_{v,d} = F_{v,d} - T_d$ with symmetric zero-centered diverging stretch ($[-V_{\max}, +V_{\max}]$); stationary objects cancel while moving targets appear as crisp positive-to-negative dipoles.
4. **Mode 4 (`motion_tracked`):** Shantanu's Idea 1 co-moving reference frame pinning the target's $(\alpha, \delta)$ at pixel center $(u_0, v_0)$ across all epochs while background stars drift past.
5. **Mode 5 (`spectral_color`):** Shantanu's Idea 2 infrared-to-visible spectral superposition and multi-band CIE 1931 RGB false color synthesis with Lupton (2004) Asinh color compression.
6. **Mode 6 (`wavelength_matched`):** Aligned single-exposure pairs matched across visits within $\pm 0.5$ channel tolerance ($|\Delta\lambda|/\lambda < 1/(2R_d)$) with monochromatic LVF hue tinting.
7. **Mode 7 (`within_visit_fast`):** Rapid intra-visit single exposure sequence ($1\text{--}3\text{ days}$) with LVF tinting, optimized for identifying fast solar-system asteroids.
* **Specialized Mode (`shift_stack`):** Co-adds exposures shifted along trial velocity vector $\vec{\mu}$ to boost faint candidate SNR by $\sqrt{N}$.

---

## 3. Quick Start

### 1. Launch the Server
```powershell
.\run_server.ps1 -Port 8080
```
Open your browser at: **`http://localhost:8080/`**

### 2. Run the Verification Test Suite
```powershell
$py = "C:\Users\shant\AppData\Roaming\uv\python\cpython-3.12.16-windows-x86_64-none\python.exe"
& $py -m unittest discover -s tests -p "test_*.py" -v
```

---

## 4. REST API Specification (Section 9.2)

* `GET /api/health` — Returns active IRSA collections (`spherex_dr1`, `spherex_qr3`), pipeline calibration lineage, cache metrics, and instrument constants.
* `GET /api/targets` — Lists verified benchmark targets with coordinates and expected physical behavior.
* `GET /api/resolve?q=&epoch=` — Resolves coordinates, propagates proper motion and reflex parallax, and reports stale discovery epoch hazard flags.
* `GET /api/observations?q=&fov=` — Returns discovered visit clusters $V_1 \dots V_M$, detector coverage counts, and release provenance (`DR1 > QR3`).
* `GET /api/frames?q=&det=&mode=&color_mode=&stretch=` — Delivers rendered frames, complete `FrameManifest`, Still-Star flicker metrics, and overlay coordinates.
* `GET /api/spectrum?q=&epoch=` — Returns calibrated 102-channel forced aperture spectrophotometry array with detected molecular band markers.
* `GET /api/overlay/catalogs?q=&mjd=` — Returns epoch-propagated Gaia DR3 field stars, CatWISE2020 sources, and SkyBoT asteroid vectors.
* `GET /api/export.gif?target=&detector=&mode=&fps=` — Compiles and streams deterministic 256-color median-cut animated GIF with burned-in telemetry HUD.


---

## 4. Benchmark Presets Included

1. **`WISE 0855-0714`:** Coldest known brown dwarf ($250\text{ K}$, Y2 dwarf). $8.15''/\text{yr}$ westward proper motion ($128''$ drift since 2010). Strong thermal peak in $D_5/D_6$ ($4.4\text{--}5.0\,\mu\text{m}$).
2. **`Barnard's Star`:** Fastest proper motion in the sky ($10.39''/\text{yr}$). Peak in $D_1/D_2$, TiO/VO molecular bands.
3. **`Epsilon Indi Ba/Bb`:** T1+T6 brown dwarf binary ($4.70''/\text{yr}$). Deep $1.4\,\mu\text{m}$ and $1.9\,\mu\text{m}$ water vapor and $2.2\,\mu\text{m}$ methane features.
4. **`Planet X Candidate`:** Distant Trans-Neptunian Object at ~450 AU. Characteristic $2.2''$ annual reflex parallax retrograde loop. Pure 42 K blackbody emission detectable only in $D_6$.
5. **`RW Aurigae`:** Classical T Tauri variable star with circumstellar dust occultation dimming.
6. **`R Draconis`:** Mira-type pulsating variable star ($P \approx 245.6\text{ days}$).

---

## 5. System Architecture & Directory Structure

```
spherex-planet-x/
├── backend/
│   ├── server.py                        # Master HTTP server & REST API
│   ├── track1_orchestration/
│   │   ├── catalog.py                   # Benchmark targets & astrophysics
│   │   ├── resolver.py                  # Proper motion & parallax epoch propagation
│   │   ├── visit_clustering.py          # 30-day temporal gap visit clustering (V1..VM)
│   │   └── cache.py                     # Two-tier LRU + disk cache
│   ├── track2_calibration/
│   │   ├── cleaning.py                  # MP_* bitmasking, ZODI model subtraction
│   │   ├── band_balancer.py             # Akhilesh's 5-step band-balancing engine
│   │   ├── flicker_audit.py             # Automated Still-Star Photometric Audit
│   │   └── differencing.py              # Median templates, difference dipoles, shift-and-stack
│   ├── track3_spectrophotometry/
│   │   ├── molecular_fingerprints.py    # 102-channel grid & molecular band definitions
│   │   ├── spectrum_extractor.py        # Forced aperture SED extraction
│   │   └── astrometric_validator.py     # Centroid fitting & Gaia DR3 validation
│   ├── track4_rendering/
│   │   ├── wcs_engine.py                # Idea 1: Gnomonic TAN grid & relative frame positioning
│   │   ├── colorization.py              # Idea 2: Infrared-to-visible spectral superposition
│   │   ├── stretching.py                # Global detector-locked Asinh stretch
│   │   └── gif_encoder.py               # Deterministic GIF89a compiler with HUD burn-in
│   └── simulation/
│       └── synthetic_spherex.py         # Multi-epoch Level-2 SPHEREx simulation generator
├── frontend/
│   ├── index.html                       # Space mission control UI
│   ├── css/style.css                    # NASA SPHEREx dark theme styling
│   └── js/
│       ├── canvas_viewer.js             # Double-buffered canvas flipbook
│       ├── spectrum_chart.js            # Interactive 102-channel spectrophotometry chart
│       ├── audit_chart.js               # Still-Star flicker reduction chart
│       └── app.js                       # Master frontend controller
├── tests/
│   └── test_pipeline.py                 # Comprehensive unit & integration tests
├── run_server.ps1                       # 1-click startup script
└── ARCHITECTURE.md                     # Full mathematical specification
```
