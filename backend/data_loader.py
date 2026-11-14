"""
SPHEREx & WISE Real Data Loader & Astronomical Ingestion Engine
==============================================================
Ingests, parses, and processes exact real FITS science data products:
- SPHEREx Level-2 calibrated cutouts across Detectors 1 through 6 (QR2 & QR3).
- WISE AllSky and AllWISE 30-arcminute multi-band cutouts (W1, W2).
- NEOWISER multi-epoch time-series exposures (2014-2024).
- Gaia DR3 astrometric reference catalogs.

Features:
- Pure Python IEEE-754 FITS reader with zero required external binary dependencies.
- Dual Field-of-View (FOV) modes:
    * 'wide': Full 30-arcmin wide-field view (256x256 / 300x300 resampled/native).
    * 'core': Zoomed-in 6.5-arcmin high-magnification stamp (128x128 / 64x64).
- Robust astrophysical Asinh, Sqrt, and Log non-linear contrast stretching.
- Dual Flipbook modes:
    * 'spectral': SPHEREx multi-band SED progression across 0.75 um to 5.0 um.
    * 'temporal': NEOWISE multi-epoch time-series demonstrating real astrometric motion.
"""

import os
import glob
import math
import array
import gzip
from typing import Dict, List, Optional, Tuple, Any

# Root data directory
BASE_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "drive", "07 Team Workspaces", "00 Shared Data", "SPHEREx Archives"
)

# Fallback paths if directory moved
ALT_DATA_DIRS = [
    BASE_DATA_DIR,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "drive"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "SPHEREx Archives"),
]

# SPHEREx detector bandpass definitions
SPHEREX_BANDS = {
    1: {"name": "SPHEREx-D1", "range": "0.75 - 1.11 um", "center_um": 0.93, "scale_arcsec": 6.15},
    2: {"name": "SPHEREx-D2", "range": "1.11 - 1.64 um", "center_um": 1.37, "scale_arcsec": 6.15},
    3: {"name": "SPHEREx-D3", "range": "1.64 - 2.42 um", "center_um": 2.03, "scale_arcsec": 6.15},
    4: {"name": "SPHEREx-D4", "range": "2.42 - 3.82 um", "center_um": 3.12, "scale_arcsec": 6.15},
    5: {"name": "SPHEREx-D5", "range": "3.82 - 4.42 um", "center_um": 4.12, "scale_arcsec": 6.15},
    6: {"name": "SPHEREx-D6", "range": "4.42 - 5.00 um", "center_um": 4.71, "scale_arcsec": 6.15},
}

class FITSImage:
    """Encapsulates a parsed FITS image and associated WCS metadata."""
    def __init__(self, width: int, height: int, cards: Dict[str, str], raw_pixels: array.array):
        self.width = width
        self.height = height
        self.cards = cards
        self.raw_pixels = raw_pixels

        # Extract common metadata
        self.object_name = cards.get("OBJECT", cards.get("TARGET", "Unknown Target")).strip()
        self.instrument = cards.get("TELESCOP", cards.get("INSTRUME", "SPHEREx")).strip()
        self.detector = cards.get("DETECTOR", "")
        self.band = cards.get("BANDPASS", cards.get("BAND", "")).strip()
        self.date_obs = cards.get("DATE_OBS", cards.get("DATE-OBS", cards.get("DATE", ""))).strip()
        self.mjd = float(cards.get("MJD_OBS", cards.get("MJD-OBS", cards.get("MJD", 0.0))) or 0.0)
        self.bunit = cards.get("BUNIT", "MJy/sr").strip()
        self.crval1 = float(cards.get("CRVAL1", 0.0) or 0.0)
        self.crval2 = float(cards.get("CRVAL2", 0.0) or 0.0)

        # Infer pixel scale
        pc1_1 = abs(float(cards.get("PC1_1", cards.get("CD1_1", 0.0)) or 0.0))
        cdelt1 = abs(float(cards.get("CDELT1", 0.0) or 0.0))
        if pc1_1 > 0:
            self.pixel_scale_arcsec = pc1_1 * 3600.0
        elif cdelt1 > 0:
            self.pixel_scale_arcsec = cdelt1 * 3600.0
        elif "SPHEREx" in self.instrument:
            self.pixel_scale_arcsec = 6.15
        else:
            self.pixel_scale_arcsec = 2.75

        self.fov_arcmin_x = (self.width * self.pixel_scale_arcsec) / 60.0
        self.fov_arcmin_y = (self.height * self.pixel_scale_arcsec) / 60.0

def read_fits(file_path: str) -> FITSImage:
    """
    Parses standard FITS and Multi-Extension FITS (MEF) image data.
    Uses astropy.io.fits when available for optimal speed and MEF support,
    with zero-dependency pure Python fallback.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"FITS file not found: {file_path}")

    # Strategy 1: Astropy FITS reader (High-performance C/NumPy accelerated)
    try:
        from astropy.io import fits
        import numpy as np
        with fits.open(file_path) as hdul:
            target_hdu = None
            for hdu in hdul:
                if hdu.data is not None and len(getattr(hdu.data, "shape", ())) >= 2:
                    target_hdu = hdu
                    break
            if target_hdu is None:
                if len(hdul) > 1 and hdul[1].data is not None:
                    target_hdu = hdul[1]
                elif hdul[0].data is not None:
                    target_hdu = hdul[0]
                else:
                    raise ValueError(f"No image data found in {file_path}")

            cards = dict(target_hdu.header)
            if target_hdu != hdul[0]:
                for k, v in hdul[0].header.items():
                    if k not in cards:
                        cards[k] = v

            str_cards = {str(k): str(v) for k, v in cards.items()}
            data = target_hdu.data
            arr_2d = np.asarray(data, dtype=np.float32)

            # 1. Calibrated Interplanetary Zodiacal Light (ZODI) Background Subtraction
            if "ZODI" in hdul and hdul["ZODI"].data is not None:
                zodi_arr = np.asarray(hdul["ZODI"].data, dtype=np.float32)
                if zodi_arr.shape == arr_2d.shape:
                    arr_2d = arr_2d - zodi_arr
                    str_cards["ZODI_SUB"] = "True"

            # 2. Cosmic Ray & Artifact Flag Masking (SPHEREx FLAGS plane bit 0x01)
            if "FLAGS" in hdul and hdul["FLAGS"].data is not None:
                flags_arr = np.asarray(hdul["FLAGS"].data, dtype=np.int32)
                if flags_arr.shape == arr_2d.shape:
                    cr_mask = (flags_arr & 0x01) > 0
                    if np.any(cr_mask):
                        med_val = float(np.nanmedian(arr_2d[~cr_mask]) if np.any(~cr_mask) else 0.0)
                        arr_2d[cr_mask] = med_val
                        str_cards["CR_MASKED"] = str(int(np.sum(cr_mask)))

            arr_2d = np.nan_to_num(arr_2d, nan=0.0, posinf=0.0, neginf=0.0)

            while arr_2d.ndim > 2:
                arr_2d = arr_2d[0]

            height, width = int(arr_2d.shape[-2]), int(arr_2d.shape[-1])
            raw_pixels = array.array("f", arr_2d.ravel().tolist())
            return FITSImage(width, height, str_cards, raw_pixels)
    except Exception:
        pass

    # Strategy 2: Pure Python zero-dependency IEEE-754 binary parser
    opener = gzip.open if file_path.endswith(".gz") else open
    with opener(file_path, "rb") as f:
        # 1. Read Primary HDU header
        hdr_str = ""
        while True:
            block = f.read(2880).decode("latin1", errors="ignore")
            if not block:
                break
            hdr_str += block
            has_end = False
            for i in range(0, len(block), 80):
                card = block[i:i+80]
                if card.startswith("END ") or card.strip() == "END":
                    has_end = True
                    break
            if has_end:
                break

        primary_cards = _parse_header_cards(hdr_str)
        naxis = int(primary_cards.get("NAXIS", 0))

        # 2. Check if primary has image data or if extension contains it
        if naxis == 0 and primary_cards.get("EXTEND", "").strip() == "T":
            # Read Extension 1 header
            ext_hdr_str = ""
            while True:
                block = f.read(2880).decode("latin1", errors="ignore")
                if not block:
                    break
                ext_hdr_str += block
                has_end = False
                for i in range(0, len(block), 80):
                    card = block[i:i+80]
                    if card.startswith("END ") or card.strip() == "END":
                        has_end = True
                        break
                if has_end:
                    break
            cards = _parse_header_cards(ext_hdr_str)
            for k, v in primary_cards.items():
                if k not in cards:
                    cards[k] = v
        else:
            cards = primary_cards

        width = int(cards.get("NAXIS1", 0))
        height = int(cards.get("NAXIS2", 0))
        bitpix = int(cards.get("BITPIX", -32))

        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid FITS image dimensions: {width}x{height}")

        # 3. Read binary pixels
        num_pixels = width * height
        if bitpix == -32:
            raw_bytes = f.read(num_pixels * 4)
            arr = array.array("f")
            arr.frombytes(raw_bytes)
            arr.byteswap()
        elif bitpix == -64:
            raw_bytes = f.read(num_pixels * 8)
            arr = array.array("d")
            arr.frombytes(raw_bytes)
            arr.byteswap()
            arr = array.array("f", arr)
        elif bitpix == 16:
            raw_bytes = f.read(num_pixels * 2)
            arr = array.array("h")
            arr.frombytes(raw_bytes)
            arr.byteswap()
            arr = array.array("f", (float(x) for x in arr))
        elif bitpix == 32:
            raw_bytes = f.read(num_pixels * 4)
            arr = array.array("i")
            arr.frombytes(raw_bytes)
            arr.byteswap()
            arr = array.array("f", (float(x) for x in arr))
        else:
            raw_bytes = f.read(num_pixels * 4)
            arr = array.array("f", [0.0] * num_pixels)

        return FITSImage(width, height, cards, arr)

def _parse_header_cards(hdr_text: str) -> Dict[str, str]:
    cards = {}
    for i in range(0, len(hdr_text), 80):
        card = hdr_text[i:i+80]
        if "=" in card:
            k, v = card.split("=", 1)
            k = k.strip()
            # Remove inline comments after '/'
            v = v.split("/")[0].strip().strip("'")
            cards[k] = v
        if card.startswith("END"):
            break
    return cards

def compute_astrophysical_stretch(
    pixels: array.array,
    stretch_type: str = "asinh",
    beta: float = 0.05,
    p_low_percent: float = 0.01,
    p_high_percent: float = 0.995
) -> Tuple[List[int], Dict[str, float]]:
    """
    Computes robust astrophysical stretch (Asinh / Sqrt / Log / Linear)
    mapping float32 science pixels into [0, 255] uint8 display space.
    """
    # Filter valid pixels
    valid = [x for x in pixels if not math.isnan(x) and not math.isinf(x) and abs(x) < 1e12]
    if not valid:
        return [0] * len(pixels), {"p_low": 0.0, "p_med": 0.0, "p_high": 1.0, "valid_count": 0}

    valid.sort()
    n = len(valid)
    p_low = valid[int(n * p_low_percent)]
    p_med = valid[int(n * 0.50)]
    p_high = valid[int(n * p_high_percent)]

    if p_high <= p_low:
        p_high = valid[-1] if valid[-1] > p_low else p_low + 1.0

    denom = p_high - p_low
    stats = {
        "p_low": round(float(p_low), 4),
        "p_med": round(float(p_med), 4),
        "p_high": round(float(p_high), 4),
        "min": round(float(valid[0]), 4),
        "max": round(float(valid[-1]), 4),
        "valid_count": n
    }

    norm_asinh = math.asinh(1.0 / beta)
    scaled = []

    for x in pixels:
        if math.isnan(x) or math.isinf(x) or abs(x) > 1e12:
            scaled.append(0)
            continue

        v = (x - p_low) / denom
        if v <= 0.0:
            s = 0
        elif v >= 1.0:
            s = 255
        else:
            if stretch_type == "asinh":
                s = int(255.0 * (math.asinh(v / beta) / norm_asinh))
            elif stretch_type == "sqrt":
                s = int(255.0 * math.sqrt(v))
            elif stretch_type == "log":
                s = int(255.0 * (math.log10(1.0 + 9.0 * v)))
            else:  # linear
                s = int(255.0 * v)
        scaled.append(max(0, min(255, s)))

    return scaled, stats

def resample_2d(
    src_pixels: List[int],
    src_w: int,
    src_h: int,
    dst_w: int = 256,
    dst_h: int = 256
) -> List[int]:
    """Bilinear / Nearest resampling to align multi-band frames on common grid."""
    if src_w == dst_w and src_h == dst_h:
        return src_pixels

    dst = [0] * (dst_w * dst_h)
    x_ratio = src_w / dst_w
    y_ratio = src_h / dst_h

    for dy in range(dst_h):
        sy = min(int(dy * y_ratio), src_h - 1)
        row_offset = sy * src_w
        dst_offset = dy * dst_w
        for dx in range(dst_w):
            sx = min(int(dx * x_ratio), src_w - 1)
            dst[dst_offset + dx] = src_pixels[row_offset + sx]
    return dst

def extract_core_cutout(
    src_pixels: List[int],
    src_w: int,
    src_h: int,
    cutout_size: int = 128
) -> Tuple[List[int], int, int]:
    """Extracts a centered sub-window around the primary target coordinate."""
    cx, cy = src_w // 2, src_h // 2
    half = cutout_size // 2

    x0 = max(0, cx - half)
    x1 = min(src_w, cx + half)
    y0 = max(0, cy - half)
    y1 = min(src_h, cy + half)

    actual_w = x1 - x0
    actual_h = y1 - y0

    cutout = []
    for y in range(y0, y1):
        row_start = y * src_w
        cutout.extend(src_pixels[row_start + x0 : row_start + x1])

    # If edges cut off, pad or resample to target cutout_size
    if actual_w != cutout_size or actual_h != cutout_size:
        cutout = resample_2d(cutout, actual_w, actual_h, cutout_size, cutout_size)

    return cutout, cutout_size, cutout_size


class ArchiveTargetCatalog:
    """Discovers and catalogs real FITS targets in the SPHEREx archives."""

    def __init__(self):
        self.archive_dir = self._find_archive_dir()

    def _find_archive_dir(self) -> Optional[str]:
        for p in ALT_DATA_DIRS:
            if os.path.exists(p) and os.path.isdir(p):
                # Verify if contains target subdirectories
                entries = [e for e in os.listdir(p) if os.path.isdir(os.path.join(p, e))]
                if entries:
                    return p
        return None

    def list_available_targets(self) -> List[Dict[str, Any]]:
        """Lists all real data targets discovered on disk with inventory."""
        targets = []
        if not self.archive_dir:
            return targets

        # Target metadata lookups
        known_metadata = {
            "Barnards Star": {
                "key": "barnards_star",
                "name": "Barnard's Star (V2500 Oph)",
                "ra": 269.4464,
                "dec": 4.7667,
                "pmra": -801.55,
                "pmdec": 10362.39,
                "type": "High Proper Motion M-Dwarf Benchmark",
                "distance_pc": 1.83,
                "description": "Fastest proper motion star in the sky (10.39 arcsec/yr). Core calibration target for SPHEREx LVF & NEOWISE multi-epoch baseline."
            },
            "Epsilon Indi B": {
                "key": "epsilon_indi_b",
                "name": "Epsilon Indi B (Brown Dwarf Binary)",
                "ra": 332.3087,
                "dec": -56.7865,
                "pmra": 3961.4,
                "pmdec": -2538.7,
                "type": "Sub-Stellar T-Dwarf Benchmark",
                "distance_pc": 3.64,
                "description": "Cold brown dwarf binary benchmark (T1 + T6) with prominent methane absorption in SPHEREx Bands 5 & 6."
            },
            "R Draconis": {
                "key": "r_draconis",
                "name": "R Draconis (Mira Variable)",
                "ra": 248.3375,
                "dec": 66.7025,
                "pmra": -12.4,
                "pmdec": 3.8,
                "type": "Pulsating Red Giant / Variable Star",
                "distance_pc": 650.0,
                "description": "Long-period variable star demonstrating extreme infrared color amplitude across SPHEREx detectors."
            }
        }

        for folder_name in sorted(os.listdir(self.archive_dir)):
            folder_path = os.path.join(self.archive_dir, folder_name)
            if not os.path.isdir(folder_path):
                continue

            fits_files = glob.glob(os.path.join(folder_path, "*.fits*"))
            if not fits_files:
                continue

            # Identify target info
            info = known_metadata.get(folder_name, {
                "key": folder_name.lower().replace(" ", "_"),
                "name": folder_name,
                "ra": 0.0,
                "dec": 0.0,
                "pmra": 0.0,
                "pmdec": 0.0,
                "type": "Astronomical Archive Target",
                "distance_pc": 0.0,
                "description": f"Target dataset with {len(fits_files)} calibrated FITS images."
            })

            # Count missions
            spherex_count = len([f for f in fits_files if "spherex" in os.path.basename(f).lower()])
            wise_count = len([f for f in fits_files if "wise" in os.path.basename(f).lower()])

            target_entry = {
                **info,
                "folder_name": folder_name,
                "folder_path": folder_path,
                "total_fits_files": len(fits_files),
                "spherex_fits_count": spherex_count,
                "wise_fits_count": wise_count,
                "has_real_fits": True
            }
            targets.append(target_entry)

        return targets

    def has_real_data(self, target_name_or_key: str) -> bool:
        """Checks if calibrated real FITS files exist for the target."""
        if not self.archive_dir:
            return False
        search_key = target_name_or_key.lower().replace(" ", "_").replace("'", "").replace("-", "_")
        for folder_name in os.listdir(self.archive_dir):
            clean_name = folder_name.lower().replace(" ", "_").replace("'", "").replace("-", "_")
            if search_key in clean_name or clean_name in search_key or folder_name.lower() == target_name_or_key.lower():
                fpath = os.path.join(self.archive_dir, folder_name)
                if os.path.isdir(fpath) and len(glob.glob(os.path.join(fpath, "*.fits*"))) > 0:
                    return True
        return False

    def get_gaia_stars(
        self,
        target_name_or_key: str,
        grid_size: int = 256,
        fov_arcmin: float = 30.0
    ) -> List[Dict[str, Any]]:
        """Extracts real Gaia DR3 cataloged field stars with pixel coordinates."""
        if not self.archive_dir:
            return []
        target_dir = None
        for folder_name in os.listdir(self.archive_dir):
            clean_name = folder_name.lower().replace(" ", "_").replace("'", "")
            search_key = target_name_or_key.lower().replace(" ", "_").replace("'", "")
            if search_key in clean_name or clean_name in search_key:
                target_dir = os.path.join(self.archive_dir, folder_name)
                break
        if not target_dir:
            return []

        csvs = glob.glob(os.path.join(target_dir, "*gaia*.csv"))
        if not csvs:
            return []

        stars = []
        import csv
        try:
            with open(csvs[0], "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if not rows:
                    return []
                center_ra = float(rows[0].get("ra", 0.0))
                center_dec = float(rows[0].get("dec", 0.0))
                cos_dec = math.cos(math.radians(center_dec))

                for idx, row in enumerate(rows[:30]):
                    try:
                        ra = float(row.get("ra", 0.0))
                        dec = float(row.get("dec", 0.0))
                        dra_arcmin = (ra - center_ra) * cos_dec * 60.0
                        ddec_arcmin = (dec - center_dec) * 60.0

                        px = (grid_size / 2.0) - (dra_arcmin / fov_arcmin) * grid_size
                        py = (grid_size / 2.0) - (ddec_arcmin / fov_arcmin) * grid_size

                        if 0 <= px < grid_size and 0 <= py < grid_size:
                            stars.append({
                                "id": idx + 1,
                                "source_id": row.get("source_id", str(idx + 1)),
                                "x": round(px, 1),
                                "y": round(py, 1),
                                "teff": 4500.0,
                                "g_mag": float(row.get("phot_g_mean_mag", 15.0) or 15.0)
                            })
                    except (ValueError, TypeError):
                        continue
        except Exception:
            pass
        return stars

    def get_target_frames(
        self,
        target_name_or_key: str,
        fov_mode: str = "wide",
        blink_mode: str = "spectral",
        stretch_type: str = "asinh",
        resample_grid: bool = True,
        target_radec: Optional[Tuple[float, float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Loads and processes real FITS frames for the given target.
        fov_mode: 'wide' (30' wide field) or 'core' (6.5' center stamp).
        blink_mode: 'spectral' (SPHEREx D1-D6) or 'temporal' (NEOWISE 2014-2024 time series).
        """
        if not self.archive_dir:
            return []

        # Find directory matching target
        target_dir = None
        for folder_name in os.listdir(self.archive_dir):
            clean_name = folder_name.lower().replace(" ", "_")
            search_key = target_name_or_key.lower().replace(" ", "_").replace("'", "")
            if search_key in clean_name or clean_name in search_key or folder_name.lower() == target_name_or_key.lower():
                target_dir = os.path.join(self.archive_dir, folder_name)
                break

        if not target_dir or not os.path.exists(target_dir):
            return []

        frames = []
        all_fits = sorted(glob.glob(os.path.join(target_dir, "*.fits*")))

        if blink_mode == "temporal":
            # Multi-Epoch Mode: Pick NEOWISER time-series and AllSky/AllWISE
            temporal_fits = [
                f for f in all_fits
                if "neowise" in os.path.basename(f).lower() and ("w1" in os.path.basename(f).lower() or "w2" in os.path.basename(f).lower())
            ]
            if not temporal_fits:
                temporal_fits = [
                    f for f in all_fits
                    if "wise" in os.path.basename(f).lower() and ("w1" in os.path.basename(f).lower() or "w2" in os.path.basename(f).lower())
                ]
            if not temporal_fits:
                temporal_fits = [f for f in all_fits if "wise" in os.path.basename(f).lower()]

            # Sample up to 12 evenly spaced epochs for smooth blink playback
            if len(temporal_fits) > 12:
                step = max(1, len(temporal_fits) // 12)
                selected_files = temporal_fits[::step]
            else:
                selected_files = temporal_fits
        else:
            # Spectral Mode: SPHEREx D1 to D6 cutouts
            spherex_files = [f for f in all_fits if "spherex" in os.path.basename(f).lower() and "level2" in os.path.basename(f).lower()]
            if not spherex_files:
                spherex_files = [f for f in all_fits if "spherex" in os.path.basename(f).lower()]

            # Pick exactly one optimal file per detector D1 through D6
            detector_map = {}
            for f in spherex_files:
                base = os.path.basename(f).upper()
                for d in range(1, 7):
                    if f"D{d}" in base or f"DET{d}" in base:
                        if d not in detector_map:
                            detector_map[d] = f
                        break
            if detector_map:
                selected_files = [detector_map[d] for d in sorted(detector_map.keys())]
            else:
                selected_files = spherex_files[:6]

        for idx, fpath in enumerate(selected_files):
            try:
                fits_img = read_fits(fpath)
            except Exception:
                continue

            # Compute astrophysical stretch
            scaled_pixels, stats = compute_astrophysical_stretch(
                fits_img.raw_pixels,
                stretch_type=stretch_type
            )

            # Extract FOV
            if fov_mode == "core":
                # High-magnification 6.5' core stamp
                target_dim = 128
                out_pixels, out_w, out_h = extract_core_cutout(
                    scaled_pixels,
                    fits_img.width,
                    fits_img.height,
                    cutout_size=target_dim
                )
                fov_arcmin = round((target_dim * fits_img.pixel_scale_arcsec) / 60.0, 2)
            else:
                # Wide-field 30' view
                if resample_grid:
                    target_dim = 256
                    out_pixels = resample_2d(
                        scaled_pixels,
                        fits_img.width,
                        fits_img.height,
                        dst_w=target_dim,
                        dst_h=target_dim
                    )
                    out_w, out_h = target_dim, target_dim
                else:
                    out_pixels = scaled_pixels
                    out_w, out_h = fits_img.width, fits_img.height
                fov_arcmin = round(max(fits_img.fov_arcmin_x, fits_img.fov_arcmin_y), 2)

            # Build detector and band description
            fname_upper = os.path.basename(fpath).upper()
            det_num = None
            if "SPHEREX" in fname_upper:
                for d in range(1, 7):
                    if f"D{d}" in fname_upper or f"DET{d}" in fname_upper or f"_{d}D" in fname_upper:
                        det_num = d
                        break

            shot_label: Optional[Dict[str, Any]] = None
            if det_num and det_num in SPHEREX_BANDS:
                binfo = SPHEREX_BANDS[det_num]
                band_label = binfo["name"]
                wavelength_um = binfo["center_um"]
                wavelength_range = binfo["range"]
                instrument_tag = "SPHEREx Level-2 Cutout"
                # Track 2 Step 1: the wavelength the target was actually seen at, from the
                # file's spectral WCS, and its band (needs astropy and the target position)
                if target_radec is not None:
                    try:
                        from backend.track2_calibration.spectral_labels import label_spherex_shot
                        shot_label = label_spherex_shot(fpath, target_radec[0], target_radec[1])
                        wavelength_um = shot_label["lambda_at_target"]
                        band_label = f"{binfo['name']} band {shot_label['band']}"
                    except Exception as exc:  # no astropy, no WCS-WAVE, not a SPHEREx MEF...
                        shot_label = {"status": "not_labelled", "reason": str(exc)[:200]}
            elif "W1" in fname_upper:
                band_label = "WISE W1"
                wavelength_um = 3.4
                wavelength_range = "3.4 um (MIR)"
                instrument_tag = "WISE / NEOWISE"
            elif "W2" in fname_upper:
                band_label = "WISE W2"
                wavelength_um = 4.6
                wavelength_range = "4.6 um (MIR)"
                instrument_tag = "WISE / NEOWISE"
            else:
                band_label = f"Frame {idx+1}"
                wavelength_um = 1.0 + idx * 0.5
                wavelength_range = f"{wavelength_um:.1f} um"
                instrument_tag = fits_img.instrument or "Astronomical Archive"

            # Parse date / year
            date_str = fits_img.date_obs
            import re
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(fpath))
            if date_match and ("neowiser" in fpath.lower() or "wise" in fpath.lower()):
                date_str = date_match.group(1)

            if not date_str:
                date_str = "2025-05-15"

            epoch_year = 2025.0
            if len(date_str) >= 4 and date_str[:4].isdigit():
                try:
                    epoch_year = float(date_str[:4])
                    if len(date_str) >= 7 and date_str[4] == "-":
                        month = float(date_str[5:7])
                        epoch_year += (month - 1) / 12.0
                except ValueError:
                    pass

            frame_data = {
                "frame_index": idx,
                "frame_id": f"real_f{idx+1}",
                "label": f"{band_label} ({wavelength_range})",
                "instrument": instrument_tag,
                "band": band_label,
                "wavelength_um": wavelength_um,
                "wavelength_range": wavelength_range,
                "date_obs": date_str,
                "epoch_year": round(epoch_year, 2),
                "mjd": fits_img.mjd,
                "fov_arcmin": fov_arcmin,
                "pixel_scale_arcsec": round(fits_img.pixel_scale_arcsec, 2),
                "width": out_w,
                "height": out_h,
                "pixels": out_pixels,
                "is_real_data": True,
                "source_file": os.path.basename(fpath),
                "stats": stats,
                "zodi_subtracted": bool(fits_img.cards.get("ZODI_SUB")),
                "cosmic_rays_masked": int(fits_img.cards.get("CR_MASKED", "0")),
                "crval": {"ra": fits_img.crval1, "dec": fits_img.crval2}
            }
            if shot_label is not None:
                frame_data["shot"] = shot_label
            frames.append(frame_data)

        return frames

# Singleton instance
target_catalog = ArchiveTargetCatalog()
