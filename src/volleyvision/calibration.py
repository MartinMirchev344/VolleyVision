"""Manual, normalized image-plane court geometry; this is not a homography."""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

from volleyvision.video import file_sha256, reference_frame

Point = tuple[float, float]
Mode = Literal["strict_court", "court_plus_free_zone"]


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _intersects(a: Point, b: Point, c: Point, d: Point) -> bool:
    if max(a[0], b[0]) < min(c[0], d[0]) or max(c[0], d[0]) < min(a[0], b[0]):
        return False
    if max(a[1], b[1]) < min(c[1], d[1]) or max(c[1], d[1]) < min(a[1], b[1]):
        return False
    return _cross(a, b, c) * _cross(a, b, d) <= 0 and _cross(c, d, a) * _cross(c, d, b) <= 0


def validate_polygon(points: list[Point]) -> None:
    if len(points) < 3:
        raise ValueError("A polygon needs at least three distinct vertices.")
    if any(len(p) != 2 or any(not isfinite(v) or not 0 <= v <= 1 for v in p) for p in points):
        raise ValueError("Polygon coordinates must be finite normalized x/y values in [0, 1].")
    if len(set(map(tuple, points))) != len(points):
        raise ValueError("Polygon vertices must be distinct; do not repeat the first vertex.")
    if abs(cv2.contourArea(np.asarray(points, dtype=np.float32))) < 1e-8:
        raise ValueError("Polygon has zero or negligible area.")
    count = len(points)
    for i in range(count):
        for j in range(i + 1, count):
            if j == i + 1 or (i == 0 and j == count - 1):
                continue
            if _intersects(points[i], points[(i + 1) % count], points[j], points[(j + 1) % count]):
                raise ValueError("Polygon edges must not cross or touch nonadjacent edges.")


@dataclass(frozen=True)
class CourtCalibration:
    court_polygon: list[Point]
    playable_polygon: list[Point] | None
    source_width: int
    source_height: int
    source_frame_index: int
    source_sha256: str
    author: str
    created_at: str
    mode: Mode = "court_plus_free_zone"
    margin_fraction: float = 0.01
    version: int = 1

    def __post_init__(self) -> None:
        validate_polygon(self.court_polygon)
        if self.playable_polygon is not None:
            validate_polygon(self.playable_polygon)
        if self.mode not in ("strict_court", "court_plus_free_zone"):
            raise ValueError("Unknown court filter mode.")
        if self.mode == "court_plus_free_zone" and self.playable_polygon is None:
            raise ValueError("Free-zone mode requires an explicit playable polygon.")
        if self.source_width <= 0 or self.source_height <= 0 or self.source_frame_index < 0:
            raise ValueError("Source dimensions must be positive and source frame nonnegative.")
        if not isfinite(self.margin_fraction) or not 0 <= self.margin_fraction <= 0.25:
            raise ValueError("Margin must be a fraction of the shorter image side, in [0, 0.25].")
        if self.version != 1:
            raise ValueError("Unsupported calibration version.")
        if len(self.source_sha256) != 64 or any(
            c not in "0123456789abcdef" for c in self.source_sha256
        ):
            raise ValueError("Calibration needs the source video's SHA256.")
        if not self.author.strip():
            raise ValueError("Calibration author is required.")

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "CourtCalibration":
        return cls(**json.loads(path.read_text(encoding="utf-8")))

    def polygon_pixels(self, width: int, height: int) -> np.ndarray:
        if width <= 0 or height <= 0:
            raise ValueError("Frame dimensions must be positive.")
        if abs(width / height - self.source_width / self.source_height) > 0.001:
            raise ValueError("Frame aspect ratio changed; recalibrate the video.")
        points = self.court_polygon if self.mode == "strict_court" else self.playable_polygon
        return np.asarray(points, dtype=np.float32) * (width, height)

    def classify(self, bbox: list[float], width: int, height: int) -> str:
        if len(bbox) != 4 or not all(isfinite(v) for v in bbox):
            raise ValueError("Bounding box must contain four finite xyxy values.")
        x1, y1, x2, y2 = bbox
        if x2 <= x1 or y2 <= y1:
            raise ValueError("Bounding box must have positive width and height.")
        polygon = self.polygon_pixels(width, height).astype(np.float32)
        distance = cv2.pointPolygonTest(polygon, ((x1 + x2) / 2, y2), True)
        tolerance = self.margin_fraction * min(width, height)
        if distance < -tolerance:
            return "excluded"
        if distance <= tolerance:
            return "uncertain"
        return "eligible"


def calibrate_interactively(
    video: Path, output: Path, author: str, frame_index: int, mode: Mode, margin: float
) -> None:
    source = reference_frame(video, frame_index)
    height, width = source.shape[:2]
    scale = min(1.0, 1280 / width, 800 / height)
    preview = cv2.resize(source, (round(width * scale), round(height * scale)))
    ph, pw = preview.shape[:2]
    selected: list[Point] = []
    polygons: list[list[Point]] = []
    stages = ["court", "playable free zone"] if mode == "court_plus_free_zone" else ["court"]
    window = "Court calibration"

    def click(event: int, x: int, y: int, flags: int, parameter: object) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            selected.append((x / pw, y / ph))

    cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(window, click)
    try:
        for stage in stages:
            selected.clear()
            message = ""
            while True:
                canvas = preview.copy()
                for polygon in polygons:
                    cv2.polylines(
                        canvas, [np.int32(np.asarray(polygon) * (pw, ph))], True, (0, 180, 0), 2
                    )
                pixels = np.int32(np.asarray(selected).reshape(-1, 2) * (pw, ph))
                if len(pixels):
                    cv2.polylines(canvas, [pixels], len(pixels) >= 3, (0, 220, 255), 2)
                cv2.putText(
                    canvas,
                    f"{stage}: click | U undo | R reset | Enter accept | Esc cancel",
                    (8, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.48,
                    (255, 255, 255),
                    1,
                )
                cv2.putText(
                    canvas, message, (8, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 100, 255), 1
                )
                cv2.imshow(window, canvas)
                key = cv2.waitKey(30) & 0xFF
                if key == 27 or cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                    raise ValueError("Calibration cancelled; no calibration was saved.")
                if key in (ord("u"), 8) and selected:
                    selected.pop()
                if key == ord("r"):
                    selected.clear()
                if key in (10, 13):
                    try:
                        validate_polygon(selected)
                    except ValueError as exc:
                        message = str(exc)
                    else:
                        polygons.append(list(selected))
                        break
        CourtCalibration(
            polygons[0],
            polygons[1] if len(polygons) > 1 else None,
            width,
            height,
            frame_index,
            file_sha256(video),
            author,
            datetime.now(UTC).isoformat(),
            mode,
            margin,
        ).save(output)
    finally:
        cv2.destroyWindow(window)
