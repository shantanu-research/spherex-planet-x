"""Coordinate parsing and matching of typed coordinates to installed test-target fields."""
import pytest

from backend.targets import resolve


@pytest.mark.parametrize("query", [
    "133.7951, -7.2451",
    "08h55m10.831s -7d14m42.53s",   # format used in the challenge statement
    "08:55:10.831 -07:14:42.53",
])
def test_wise_0855_coordinates_load_installed_field(query):
    target = resolve(query)
    assert target["id"] == "wise_0855"
    assert target["matched_from_query"] == query
    assert target["match_separation_arcmin"] < 0.05


def test_far_coordinates_stay_a_user_field():
    target = resolve("10, 20")
    assert target["id"].startswith("field_")
    assert target["pm_ra_mas"] == 0.0


def test_simulated_field_is_never_substituted_for_coordinates():
    target = resolve("48.25, 12.8")  # exact position of the simulated preset
    assert target["id"] != "planet_x_candidate"


@pytest.mark.parametrize("query", ["400, 10", "12:00 +95:00"])
def test_out_of_range_coordinates_are_rejected(query):
    with pytest.raises(ValueError):
        resolve(query)
