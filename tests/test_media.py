import shutil
import unittest
from backend.media import gif_to_mp4

class MediaTests(unittest.TestCase):
    def test_invalid_image_is_rejected(self):
        with self.assertRaises(ValueError):
            gif_to_mp4(b'not an image')

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg required')
    def test_real_mp4_container(self):
        import base64
        gif = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
        result = gif_to_mp4(gif)
        self.assertEqual(result[4:8], b'ftyp')

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg required')
    def test_pipeline_animation_is_decodable_not_just_a_gif_header(self):
        from backend.pipeline import generate_gif_export
        from PIL import Image
        import io
        data=generate_gif_export("Barnard's Star",'D1','visit_blink',4,source_mode='simulated')
        image=Image.open(io.BytesIO(data))
        self.assertGreater(image.n_frames,1)
        for i in range(image.n_frames):
            image.seek(i); image.load()
        result=gif_to_mp4(data)
        self.assertEqual(result[4:8],b'ftyp')
