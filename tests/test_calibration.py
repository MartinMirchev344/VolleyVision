from dataclasses import replace

import numpy as np
import pytest

from volleyanalytics.calibration import CourtCalibration, validate_polygon


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


# A court seen from behind the near end line: the far end is narrower and higher.
PERSPECTIVE_COURT = [(500, 400), (800, 400), (1150, 650), (130, 650)]  # deliberately unordered


@pytest.fixture
def end_line_view():
    width, height = 1280, 720
    points = [(x / width, y / height) for x, y in PERSPECTIVE_COURT]
    return CourtCalibration(
        points,
        None,
        width,
        height,
        0,
        "a" * 64,
        "test",
        "2026-11-28T00:00:00+00:00",
        mode="strict_court",
    )


def _foot_at(calibration, x_m, y_m):
    """A player box whose feet stand at court position (x_m, y_m)."""
    import cv2

    inverse = np.linalg.inv(calibration.court_transform(1280, 720)).astype(np.float32)
    x, y = cv2.perspectiveTransform(np.float32([[[x_m, y_m]]]), inverse)[0, 0]
    return [x - 10, y - 80, x + 10, y]


def test_corners_are_ordered_near_left_first():
    from volleyanalytics.calibration import ordered_corners

    assert ordered_corners(PERSPECTIVE_COURT).tolist() == [
        [130, 650],
        [1150, 650],
        [800, 400],
        [500, 400],
    ]
    with pytest.raises(ValueError, match="four corners"):
        ordered_corners(PERSPECTIVE_COURT[:3])


def test_court_position_in_metres(end_line_view):
    assert end_line_view.court_position([120, 570, 140, 650], 1280, 720) == pytest.approx(
        (0, 0), abs=1e-3
    )
    assert end_line_view.court_position(_foot_at(end_line_view, 4.5, 4), 1280, 720) == (
        pytest.approx((4.5, 4), abs=1e-3)
    )
    centre = end_line_view.centre_line_pixels(1280, 720)
    back = [end_line_view.court_position([x - 1, y - 5, x + 1, y], 1280, 720) for x, y in centre]
    assert back == [pytest.approx((0, 9), abs=1e-3), pytest.approx((9, 9), abs=1e-3)]


def test_court_side_with_tolerance_at_the_net(end_line_view):
    side = end_line_view.court_side
    assert side(_foot_at(end_line_view, 4.5, 3), 1280, 720) == "near"
    assert side(_foot_at(end_line_view, 4.5, -2), 1280, 720) == "near"  # server behind end line
    assert side(_foot_at(end_line_view, 4.5, 9.3), 1280, 720) == "near"  # within 0.5 m
    assert side(_foot_at(end_line_view, 4.5, 9.7), 1280, 720) == "far"
    assert side(_foot_at(end_line_view, 4.5, 9.7), 1280, 720, net_tolerance_m=1.0) == "near"
    assert side(_foot_at(end_line_view, 4.5, 15), 1280, 720) == "far"
    # Feet above the floor's horizon (e.g. a spectator high in the stands) are never near.
    assert side([600, 0, 620, 40], 1280, 720) == "far"
