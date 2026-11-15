import unittest
from unittest.mock import patch

from backend.track1.archive import build_query
from backend.track1_orchestration.catalog import get_target_by_query
from backend.track3_spectrophotometry.spectrum_extractor import extract_102_channel_spectrum


class SourceIntegrityTests(unittest.TestCase):
    def test_unknown_and_empty_targets_do_not_select_a_default(self):
        for name in ('', 'not a real benchmark'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                get_target_by_query(name)

    def test_invalid_archive_coordinates_and_detectors_are_rejected(self):
        for ra, dec, detector in [(360, 0, None), (0, 91, None), (0, 0, 'SPHEREX-D9')]:
            with self.subTest(ra=ra, dec=dec, detector=detector), self.assertRaises(ValueError):
                build_query(ra, dec, detector)

    @patch('backend.track3_spectrophotometry.spectrum_extractor.extract_real_cutout_photometry', return_value=None)
    @patch('backend.track3_spectrophotometry.spectrum_extractor.extract_synthetic_spectrum')
    def test_missing_real_spectrum_does_not_generate_one(self, synthetic, real):
        result = extract_102_channel_spectrum({}, 'real')
        self.assertEqual(result['status'], 'unavailable')
        synthetic.assert_not_called()

    @patch('backend.track3_spectrophotometry.spectrum_extractor.extract_synthetic_spectrum', return_value={'source': 'synthetic'})
    def test_viewer_simulated_source_is_supported(self, synthetic):
        self.assertEqual(extract_102_channel_spectrum({}, 'simulated')['source'], 'synthetic')
        synthetic.assert_called_once()
