"""Encode an actual MP4 from the same rendered frames used by GIF export."""
import subprocess
import tempfile
from pathlib import Path


def gif_to_mp4(gif_bytes: bytes) -> bytes:
    if not gif_bytes.startswith((b'GIF87a', b'GIF89a')):
        raise ValueError('No valid animation available for export')
    with tempfile.TemporaryDirectory(prefix='spherex-export-') as directory:
        source, output = Path(directory) / 'input.gif', Path(directory) / 'output.mp4'
        source.write_bytes(gif_bytes)
        try:
            subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(source),
                            '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264',
                            '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(output)],
                           check=True, capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError('MP4 encoding failed; verify ffmpeg is installed') from exc
        return output.read_bytes()
