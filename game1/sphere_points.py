"""Spherical point cloud for the planetary viewer (issue #11).

Issue #11 asks for "millions of cells, or points, placed in spherical
coordinates", on the assumption that each point can later be associated with
a 3D model that only renders past a certain zoom. This module deliberately
sidesteps the heavy hex-polygon meshing of :mod:`game1.hex_sphere`:

- a Fibonacci lattice samples ``count`` evenly distributed unit-sphere
  directions deterministically;
- biome and elevation are derived from latitude and a hash-noise function so
  the cloud is fully reproducible without storing per-point data;
- a multi-LOD payload packs several point counts so the WebGL viewer can swap
  between them by current zoom, the same pattern :mod:`game1.hex_sphere`
  already uses for the dual-mesh ladder.

Each point is described only by its unit-vector position, biome index and
elevation. That is enough for a GPU to draw it as a billboard, and for
future versions to attach a per-point building or moving-transport sprite by
id without reshaping the data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import asin, atan2, cos, degrees, floor, pi, sin, sqrt
from typing import Iterable, Sequence

from .hex_sphere import DEFAULT_TENTH_EARTH_RADIUS_M


Vec3 = tuple[float, float, float]


BIOME_PALETTE: tuple[tuple[str, str], ...] = (
    ("ocean", "#2f6f9a"),
    ("polar", "#e6f1f3"),
    ("tundra", "#a7b8a0"),
    ("boreal", "#46734f"),
    ("temperate", "#74a35a"),
    ("steppe", "#c2b15c"),
    ("desert", "#d29a4d"),
    ("tropical", "#27905b"),
)
BIOME_INDEX = {name: index for index, (name, _color) in enumerate(BIOME_PALETTE)}


@dataclass(frozen=True)
class SpherePointLevel:
    """A single LOD level: a flat array of unit-sphere points and metadata.

    The arrays are kept parallel rather than as objects-per-point so the
    payload stays compact (one f32 triple + one u8 + one i16 per point) and
    can be uploaded to a GPU buffer in one call.
    """

    count: int
    positions: tuple[Vec3, ...]
    biomes: tuple[int, ...]
    elevations_m: tuple[int, ...]
    seed: int

    def to_render_dict(self) -> dict[str, object]:
        flat_positions: list[float] = []
        for x, y, z in self.positions:
            flat_positions.append(round(x, 6))
            flat_positions.append(round(y, 6))
            flat_positions.append(round(z, 6))
        return {
            "count": self.count,
            "seed": self.seed,
            "positions": flat_positions,
            "biomes": list(self.biomes),
            "elevations": list(self.elevations_m),
        }


@dataclass(frozen=True)
class SpherePointPayload:
    """Multi-LOD payload of spherical point clouds for a WebGL viewer."""

    planet_radius_m: float
    target_logical_count: int
    biome_palette: tuple[tuple[str, str], ...]
    levels: tuple[SpherePointLevel, ...]
    zoom_thresholds: tuple[float, ...] = field(default_factory=tuple)

    def to_render_payload(self) -> dict[str, object]:
        return {
            "kind": "sphere-points-lod",
            "planetRadiusM": self.planet_radius_m,
            "targetLogicalCount": self.target_logical_count,
            "biomes": [
                {"name": name, "color": color} for name, color in self.biome_palette
            ],
            "zoomThresholds": list(self.zoom_thresholds),
            "levels": [level.to_render_dict() for level in self.levels],
        }


def build_sphere_point_level(
    *,
    count: int,
    seed: int = 1,
) -> SpherePointLevel:
    """Sample ``count`` evenly distributed unit-sphere points.

    Uses a Fibonacci lattice (golden-angle spiral). It gives near-uniform
    coverage without requiring a triangulation, which is exactly what the
    issue asks for: "точки, расположенные в сферических координатах".
    """

    if count < 1:
        raise ValueError("count must be positive")

    golden_angle = pi * (3.0 - sqrt(5.0))
    positions: list[Vec3] = []
    biomes: list[int] = []
    elevations: list[int] = []

    for index in range(count):
        # Even spacing of z in [-1, 1].
        z = 1.0 - (2.0 * index + 1.0) / count
        radius_xy = sqrt(max(0.0, 1.0 - z * z))
        theta = golden_angle * index
        x = cos(theta) * radius_xy
        y = sin(theta) * radius_xy

        latitude = degrees(asin(max(-1.0, min(1.0, z))))
        biome, elevation_m = _biome_and_elevation((x, y, z), latitude, seed + index)
        positions.append((x, y, z))
        biomes.append(BIOME_INDEX[biome])
        elevations.append(elevation_m)

    return SpherePointLevel(
        count=count,
        positions=tuple(positions),
        biomes=tuple(biomes),
        elevations_m=tuple(elevations),
        seed=seed,
    )


def build_sphere_point_payload(
    *,
    counts: Iterable[int] = (2_000, 20_000, 200_000),
    target_logical_count: int = 10_000_000,
    planet_radius_m: float = DEFAULT_TENTH_EARTH_RADIUS_M,
    zoom_thresholds: Sequence[float] | None = None,
    seed: int = 1,
) -> SpherePointPayload:
    """Build a multi-LOD spherical point payload for the WebGL viewer.

    ``counts`` lists the number of points per LOD, lowest density first.
    ``target_logical_count`` is what the server-side simulation logically
    addresses (millions to billions of points); the client only ever holds
    one of the smaller LODs at a time, so the renderer scales.
    """

    sorted_counts = sorted({int(value) for value in counts})
    if not sorted_counts:
        raise ValueError("counts must contain at least one entry")
    if any(value < 1 for value in sorted_counts):
        raise ValueError("each count must be positive")
    if target_logical_count < sorted_counts[-1]:
        raise ValueError(
            "target_logical_count must be at least the largest LOD count"
        )

    levels = tuple(
        build_sphere_point_level(count=count, seed=seed)
        for count in sorted_counts
    )

    if zoom_thresholds is None:
        thresholds: tuple[float, ...] = tuple(
            round(1.4 + index * 0.9, 6) for index in range(len(levels) - 1)
        )
    else:
        thresholds = tuple(float(value) for value in zoom_thresholds)
        if len(thresholds) != len(levels) - 1:
            raise ValueError(
                "zoom_thresholds must have one fewer entry than counts"
            )

    return SpherePointPayload(
        planet_radius_m=planet_radius_m,
        target_logical_count=target_logical_count,
        biome_palette=BIOME_PALETTE,
        levels=levels,
        zoom_thresholds=thresholds,
    )


def _biome_and_elevation(
    point: Vec3, latitude: float, salt: int
) -> tuple[str, int]:
    base_noise = _noise(point, salt)
    if base_noise < 0.42:
        elevation = int(round(-200 + base_noise * 400))
        return "ocean", elevation

    biome = _biome_for_latitude(latitude)
    elevation_noise = _noise((point[1], point[2], point[0]), salt + 17)
    elevation = int(round(elevation_noise * 2200.0))
    return biome, elevation


def _biome_for_latitude(latitude: float) -> str:
    abs_lat = abs(latitude)
    if abs_lat >= 75:
        return "polar"
    if abs_lat >= 60:
        return "tundra"
    if abs_lat >= 45:
        return "boreal"
    if abs_lat >= 30:
        return "temperate"
    if abs_lat >= 15:
        return "steppe"
    return "tropical"


def _noise(point: Vec3, salt: int) -> float:
    value = sin(
        point[0] * 12.9898
        + point[1] * 78.233
        + point[2] * 37.719
        + salt * 0.1113
    ) * 43_758.5453
    return value - floor(value)


def lat_lon_for_point(point: Vec3) -> tuple[float, float]:
    """Convert a unit-sphere point to (latitude, longitude) degrees."""

    z = max(-1.0, min(1.0, point[2]))
    latitude = degrees(asin(z))
    longitude = degrees(atan2(point[1], point[0]))
    return latitude, longitude
