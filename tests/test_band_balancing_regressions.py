import pytest

from backend.calibration.band_balancer import fill_missing_bands, perform_band_balanced_stacking
from backend.calibration.flicker_audit import run_still_star_flicker_audit


def test_repeated_missing_bands_do_not_create_independent_measurements():
    visits = []
    for i in range(2):
        exposures = [
            {"image": [[10.0]], "cleaned_image": [[10.0 if band == 1 else None]],
             "variance": [[1.0]], "channel": band}
            for band in range(1, 11)
        ]
        visits.append({"visit_id": str(i), "visit_index": i, "mjd_mid": i,
                       "date_utc": "test", "survey_pass": "test", "exposures": exposures})

    result = perform_band_balanced_stacking(visits, "D6")
    for stack in result["visit_stacks"]:
        assert stack["stacked_image"][0][0] == pytest.approx(10.0)
        assert stack["stacked_variance"][0][0] == pytest.approx(1.0)
        assert stack["n_band_filled_pixels"] == 1


def test_interpolated_band_mean_uses_original_measurement_coefficients():
    values, variance, filled = fill_missing_bands([2.0, 0.0, 6.0], [1.0, 0.0, 0.25])
    assert values == [2.0, 4.0, 6.0]
    # The three-band mean is (A + B) / 2, with Var(A)=1 and Var(B)=4.
    assert variance == pytest.approx(1.25)
    assert filled

    _, variance, filled = fill_missing_bands([2.0, 4.0, 6.0], [1.0, 1.0, 0.25])
    assert variance == pytest.approx(6.0 / 9.0)
    assert not filled
    assert fill_missing_bands([0.0], [0.0]) is None


def test_difference_audit_without_background_reports_not_run():
    image = [
        [1.0 if (x - 10) ** 2 + (y - 10) ** 2 <= 36 else None for x in range(21)]
        for y in range(21)
    ]
    image[10][10] = 100.0
    variance = [[1.0 if value is not None else None for value in row] for row in image]
    result = run_still_star_flicker_audit(
        [{"image": image}] * 2,
        [{"stacked_image": image, "stacked_variance": variance}] * 2,
        [(10, 10)],
    )
    assert result["n_stars_audited"] == 1
    assert result["null_test_chi2_nu"] is None
    assert result["null_test_passed"] is None
    assert "No valid background blocks" in result["null_test_verdict"]
    assert result["difference_tests"][0]["status"] == "not_run"
