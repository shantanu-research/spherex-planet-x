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
