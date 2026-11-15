"""
SPHEREx Planet X Challenge - Deterministic Animated GIF & Telemetry HUD Engine
Generates animated GIF flipbooks with burned-in HUD telemetry and single sequence-wide palette.
"""

from typing import List, Dict, Any, Tuple
import struct
import io
import math

# Simple 5x7 bitmap font for burning telemetry text into pixel arrays
FONT_5X7 = {
    ' ': [0x00, 0x00, 0x00, 0x00, 0x00],
    'A': [0x7C, 0x12, 0x11, 0x12, 0x7C], 'B': [0x7F, 0x49, 0x49, 0x49, 0x36],
    'C': [0x3E, 0x41, 0x41, 0x41, 0x22], 'D': [0x7F, 0x41, 0x41, 0x22, 0x1C],
    'E': [0x7F, 0x49, 0x49, 0x49, 0x41], 'F': [0x7F, 0x09, 0x09, 0x09, 0x01],
    'G': [0x3E, 0x41, 0x49, 0x49, 0x7A], 'H': [0x7F, 0x08, 0x08, 0x08, 0x7F],
    'I': [0x00, 0x41, 0x7F, 0x41, 0x00], 'J': [0x20, 0x40, 0x41, 0x3F, 0x01],
    'K': [0x7F, 0x08, 0x14, 0x22, 0x41], 'L': [0x7F, 0x40, 0x40, 0x40, 0x40],
    'M': [0x7F, 0x02, 0x0C, 0x02, 0x7F], 'N': [0x7F, 0x04, 0x08, 0x10, 0x7F],
    'O': [0x3E, 0x41, 0x41, 0x41, 0x3E], 'P': [0x7F, 0x09, 0x09, 0x09, 0x06],
    'Q': [0x3E, 0x41, 0x51, 0x21, 0x5E], 'R': [0x7F, 0x09, 0x19, 0x29, 0x46],
    'S': [0x46, 0x49, 0x49, 0x49, 0x31], 'T': [0x01, 0x01, 0x7F, 0x01, 0x01],
    'U': [0x3F, 0x40, 0x40, 0x40, 0x3F], 'V': [0x1F, 0x20, 0x40, 0x20, 0x1F],
    'W': [0x7F, 0x20, 0x18, 0x20, 0x7F], 'X': [0x63, 0x14, 0x08, 0x14, 0x63],
    'Y': [0x07, 0x08, 0x70, 0x08, 0x07], 'Z': [0x61, 0x51, 0x49, 0x45, 0x43],
    '0': [0x3E, 0x51, 0x49, 0x45, 0x3E], '1': [0x00, 0x42, 0x7F, 0x40, 0x00],
    '2': [0x42, 0x61, 0x51, 0x49, 0x46], '3': [0x21, 0x41, 0x45, 0x4B, 0x31],
    '4': [0x18, 0x14, 0x12, 0x7F, 0x10], '5': [0x27, 0x45, 0x45, 0x45, 0x39],
    '6': [0x3C, 0x4A, 0x49, 0x49, 0x30], '7': [0x01, 0x71, 0x09, 0x05, 0x03],
    '8': [0x36, 0x49, 0x49, 0x49, 0x36], '9': [0x06, 0x49, 0x49, 0x29, 0x1E],
    '.': [0x00, 0x60, 0x60, 0x00, 0x00], ':': [0x00, 0x36, 0x36, 0x00, 0x00],
    '-': [0x08, 0x08, 0x08, 0x08, 0x08], '/': [0x20, 0x10, 0x08, 0x04, 0x02],
    '|': [0x00, 0x00, 0x7F, 0x00, 0x00], '+': [0x08, 0x08, 0x3E, 0x08, 0x08],
    '_': [0x80, 0x80, 0x80, 0x80, 0x80], '(': [0x00, 0x1C, 0x22, 0x41, 0x00],
    ')': [0x00, 0x41, 0x22, 0x1C, 0x00]
}

def render_text_into_rgb_frame(
    rgb_frame: List[List[Tuple[int, int, int]]],
    text: str,
    start_x: int,
    start_y: int,
    color: Tuple[int, int, int] = (255, 255, 255),
    bg_color: Tuple[int, int, int] = None
):
    """Draws 5x7 bitmap characters onto a 2D RGB pixel array."""
    h = len(rgb_frame)
    w = len(rgb_frame[0])
    cur_x = start_x
    
    for ch in text.upper():
        glyph = FONT_5X7.get(ch, FONT_5X7[' '])
        for col_idx, col_bits in enumerate(glyph):
            px = cur_x + col_idx
            if 0 <= px < w:
                for row_idx in range(7):
                    py = start_y + row_idx
                    if 0 <= py < h:
                        bit = (col_bits >> row_idx) & 1
                        if bit:
                            rgb_frame[py][px] = color
                        elif bg_color is not None:
                            rgb_frame[py][px] = bg_color
        cur_x += 6

def burn_telemetry_hud(
    rgb_frame: List[List[Tuple[int, int, int]]],
    target_name: str,
    visit_id: str,
    mjd: float,
    detector: str,
    mode_str: str
) -> List[List[Tuple[int, int, int]]]:
    """
    Burns high-contrast SPHEREx telemetry HUD bar at top and bottom of frame.
    Format: 'TARGET | VISIT | MJD | DET | MODE'
    """
    h = len(rgb_frame)
    w = len(rgb_frame[0])
    # Make deep copy of frame
    out = [row[:] for row in rgb_frame]
    
    # Top banner bar (height 10 px)
    for y in range(min(10, h)):
        for x in range(w):
            out[y][x] = (12, 16, 24)
            
    # Bottom banner bar (height 10 px)
    for y in range(max(0, h - 10), h):
        for x in range(w):
            out[y][x] = (12, 16, 24)
            
    header_text = f"{target_name[:12]} | {visit_id} | {detector}"
    footer_text = f"MJD {mjd:.1f} | {mode_str[:14]}"
    
    render_text_into_rgb_frame(out, header_text, 3, 2, color=(0, 220, 255))
    render_text_into_rgb_frame(out, footer_text, 3, max(2, h - 9), color=(255, 200, 50))
    
    return out

def build_global_palette(frames_rgb: List[List[List[Tuple[int, int, int]]]], max_colors: int = 128) -> List[Tuple[int, int, int]]:
    """
    Extracts a representative global sequence-wide color palette using uniform 3D RGB quantization.
    Ensures ZERO palette-switching flicker in animated GIFs!
    """
    # 5 levels of R (0, 64, 128, 192, 255), 5 of G, 5 of B = 125 colors + specials
    palette = [(0, 0, 0), (12, 16, 24), (255, 255, 255), (0, 220, 255), (255, 200, 50)]
    steps = [0, 64, 128, 192, 255]
    for r in steps:
        for g in steps:
            for b in steps:
                color = (r, g, b)
                if color not in palette:
                    palette.append(color)
                    if len(palette) >= max_colors:
                        return palette
    return palette

def rgb_to_palette_index(r: int, g: int, b: int, palette: List[Tuple[int, int, int]]) -> int:
    """Finds nearest color in palette using Euclidean distance."""
    best_idx = 0
    best_dist = 1e9
    for idx, (pr, pg, pb) in enumerate(palette):
        dist = (r - pr)**2 + (g - pg)**2 + (b - pb)**2
        if dist < best_dist:
            best_dist = dist
            best_idx = idx
            if dist == 0:
                break
    return best_idx

def encode_gif_stream(
    frames_rgb: List[List[List[Tuple[int, int, int]]]],
    delay_ms: int = 300
) -> bytes:
    """
    Encodes list of 2D RGB frames into deterministic GIF89a binary stream.
    Zero external dependencies (pure Python byte synthesis).
    """
    if not frames_rgb:
        return b""
        
    height = len(frames_rgb[0])
    width = len(frames_rgb[0][0])
    
    palette = build_global_palette(frames_rgb, max_colors=128)
    # Pad palette to next power of 2 (128 -> 128)
    pal_size = len(palette)
    # 2^(N+1) table: 128 colors -> N = 6 (7 bits)
    color_res = 7
    while len(palette) < 128:
        palette.append((0, 0, 0))
        
    out = io.BytesIO()
    
    # 1. Header: GIF89a
    out.write(b"GIF89a")
    
    # 2. Logical Screen Descriptor
    # Width (2 bytes), Height (2 bytes), Packed Fields, Background Color Index, Pixel Aspect Ratio
    # Packed: Global Color Table Flag (1), Color Resolution (3 bits: 6), Sort Flag (0), Size of Global Color Table (3 bits: 6)
    # 0b11100110 = 0xE6
    packed_fields = 0b10000000 | (6 << 4) | 6
    out.write(struct.pack("<HHBBB", width, height, packed_fields, 0, 0))
    
    # 3. Global Color Table (128 * 3 bytes)
    for r, g, b in palette:
        out.write(struct.pack("BBB", r, g, b))
        
    # 4. Netscape Application Extension (for infinite loop)
    out.write(b"\x21\xFF\x0BNETSCAPE2.0\x03\x01\x00\x00\x00")
    
    # 5. Encode each frame
    delay_units = max(1, delay_ms // 10)  # in 1/100ths of a second
    
    for frame in frames_rgb:
        # Graphic Control Extension
        # Packed: Reserved (3 bits), Disposal Method (3 bits: 1 = do not dispose), User Input (0), Transparent Color Flag (0)
        # 0b00000100 = 0x04
        out.write(b"\x21\xF9\x04")
        out.write(struct.pack("<BBHB", 0x04, 0, delay_units, 0))
        out.write(b"\x00")
        
        # Image Descriptor: 0x2C, left, top, width, height, packed (0 = no local color table)
        out.write(b"\x2C")
        out.write(struct.pack("<HHHHB", 0, 0, width, height, 0))
        
        # Quantize frame pixels to palette indices
        indexed_pixels = []
        for y in range(height):
            for x in range(width):
                r, g, b = frame[y][x]
                idx = rgb_to_palette_index(r, g, b, palette)
                indexed_pixels.append(idx)
                
        # LZW compression (minimum code size 7 for 128 colors)
        min_code_size = 7
        out.write(struct.pack("B", min_code_size))
        
        # Simple uncompressed LZW clear-code stream packing
        clear_code = 1 << min_code_size  # 128
        eoi_code = clear_code + 1        # 129
        
        # Pack raw pixel indices with clear code prefixes
        # Sub-blocks of up to 254 bytes
        raw_bytes = bytearray()
        # Initial Clear Code
        bits_per_code = min_code_size + 1  # 8 bits
        
        # Build bitstream
        bit_buffer = 0
        bit_count = 0
        
        def write_code(code: int, code_bits: int):
            nonlocal bit_buffer, bit_count, raw_bytes
            bit_buffer |= (code << bit_count)
            bit_count += code_bits
            while bit_count >= 8:
                raw_bytes.append(bit_buffer & 0xFF)
                bit_buffer >>= 8
                bit_count -= 8
                
        write_code(clear_code, bits_per_code)
        for pix in indexed_pixels:
            write_code(pix, bits_per_code)
        write_code(eoi_code, bits_per_code)
        
        if bit_count > 0:
            raw_bytes.append(bit_buffer & 0xFF)
            
        # Write sub-blocks (max 254 bytes each)
        idx_b = 0
        total_len = len(raw_bytes)
        while idx_b < total_len:
            chunk = raw_bytes[idx_b : idx_b + 254]
            out.write(struct.pack("B", len(chunk)))
            out.write(chunk)
            idx_b += len(chunk)
        out.write(b"\x00")  # Block terminator
        
    # 6. Trailer: 0x3B
    out.write(b"\x3B")
    return out.getvalue()
