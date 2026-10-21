from dataclasses import replace

import numpy as np
import pytest

from volleyvision.calibration import CourtCalibration, validate_polygon


@pytest.fixture
def court():
    return CourtCalibration(
        [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)],
        [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)],
        1000,
        500,
        0,
        "a" * 64,
        "test",
        "2026-10-21T00:00:00+00:00",
        mode="strict_court",
        margin_fraction=0.01,
    )


def test_uses_feet_not_box_center(court):
    assert court.classify([450, 50, 550, 250], 1000, 500) == "eligible"
    assert court.classify([450, 150, 550, 450], 1000, 500) == "excluded"


@pytest.mark.parametrize(
    "foot_y, expected",
    [(400, "uncertain"), (404, "uncertain"), (406, "excluded"), (390, "eligible")],
)
def test_boundary_tolerance(court, foot_y, expected):
    assert court.classify([450, 100, 550, foot_y], 1000, 500) == expected


def test_free_zone_keeps_legal_outside_play(court):
    assert court.classify([450, 150, 550, 430], 1000, 500) == "excluded"
    free = replace(court, mode="court_plus_free_zone")
    assert free.classify([450, 150, 550, 430], 1000, 500) == "eligible"


def test_normalized_geometry_scales_and_roundtrips(court, tmp_path):
    path = tmp_path / "calibration.json"
    court.save(path)
    loaded = CourtCalibration.load(path)
    assert np.allclose(loaded.polygon_pixels(500, 250), court.polygon_pixels(1000, 500) / 2)
    assert loaded.classify([225, 50, 275, 202], 500, 250) == "uncertain"
    with pytest.raises(ValueError, match="aspect ratio"):
        loaded.polygon_pixels(1000, 1000)


@pytest.mark.parametrize(
    "polygon",
    [
        [(0, 0), (1, 1)],
        [(0, 0), (0.5, 0.5), (1, 1)],
        [(0, 0), (1, 0), (1, 1), (0, 0)],
        [(0, 0), (1, 1), (0, 1), (0.8, 0)],
        [(0, 0), (float("nan"), 0), (0, 1)],
        [(0, 0), (1.1, 0), (0, 1)],
    ],
)
def test_invalid_polygons_are_rejected(polygon):
    with pytest.raises(ValueError):
        validate_polygon(polygon)


def test_invalid_modes_and_boxes(court):
    with pytest.raises(ValueError, match="explicit playable"):
        replace(court, mode="court_plus_free_zone", playable_polygon=None)
    with pytest.raises(ValueError, match="positive width"):
        court.classify([20, 20, 10, 100], 1000, 500)
    with pytest.raises(ValueError, match="Margin"):
        replace(court, margin_fraction=float("nan"))
