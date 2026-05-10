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
from math import asin, atan2, cos, degrees, floor, pi, radians, sin, sqrt
from typing import Iterable, Sequence

from .hex_sphere import DEFAULT_TENTH_EARTH_RADIUS_M


Vec3 = tuple[float, float, float]


BIOME_PALETTE: tuple[tuple[str, str], ...] = (
    ("ocean", "#2f6f9a"),
    ("lake", "#2f8fb7"),
    ("polar", "#e6f1f3"),
    ("tundra", "#a7b8a0"),
    ("boreal", "#46734f"),
    ("temperate", "#74a35a"),
    ("steppe", "#c2b15c"),
    ("desert", "#d29a4d"),
    ("tropical", "#27905b"),
    ("mountain", "#8f958d"),
)
BIOME_INDEX = {name: index for index, (name, _color) in enumerate(BIOME_PALETTE)}

FEATURE_RIVER = 1
FEATURE_LAKE = 2
FEATURE_MOUNTAIN = 4
FEATURE_ISLAND = 8


@dataclass(frozen=True)
class TerrainSample:
    """Deterministic terrain sample for one point on the unit sphere."""

    biome: str
    elevation_m: int
    features: int = 0
    river_drop_m: float = 0.0
    continent_score: float = 0.0
    moisture: float = 0.0

    @property
    def has_river(self) -> bool:
        return bool(self.features & FEATURE_RIVER)

    @property
    def has_lake(self) -> bool:
        return bool(self.features & FEATURE_LAKE)

    @property
    def has_mountain(self) -> bool:
        return bool(self.features & FEATURE_MOUNTAIN)

    @property
    def is_island(self) -> bool:
        return bool(self.features & FEATURE_ISLAND)


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
    features: tuple[int, ...]
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
            "features": list(self.features),
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
    features: list[int] = []

    for index in range(count):
        # Even spacing of z in [-1, 1].
        z = 1.0 - (2.0 * index + 1.0) / count
        radius_xy = sqrt(max(0.0, 1.0 - z * z))
        theta = golden_angle * index
        x = cos(theta) * radius_xy
        y = sin(theta) * radius_xy

        terrain = sample_point_terrain((x, y, z), seed=seed)
        positions.append((x, y, z))
        biomes.append(BIOME_INDEX[terrain.biome])
        elevations.append(terrain.elevation_m)
        features.append(terrain.features)

    return SpherePointLevel(
        count=count,
        positions=tuple(positions),
        biomes=tuple(biomes),
        elevations_m=tuple(elevations),
        features=tuple(features),
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


def point_from_lat_lon(latitude: float, longitude: float) -> Vec3:
    """Convert latitude/longitude degrees into a unit-sphere point."""

    lat = radians(latitude)
    lon = radians(longitude)
    cos_lat = cos(lat)
    return (cos_lat * cos(lon), cos_lat * sin(lon), sin(lat))


def sample_point_terrain(point: Vec3, *, seed: int = 1) -> TerrainSample:
    """Sample coherent terrain for a unit-sphere point.

    The generator uses only continuous spherical noise, not per-point hashes,
    so nearby positions tend to keep the same ocean/continent/biome identity.
    Rivers and lakes are sparse feature bits layered on top of the biome.
    """

    latitude, _longitude = lat_lon_for_point(point)
    abs_lat = abs(latitude)
    continent = _smooth_noise(point, seed + 101, base_frequency=1.05, octaves=4)
    island_score = _smooth_noise(point, seed + 151, base_frequency=6.0, octaves=3)
    moisture = 0.5 + 0.5 * _smooth_noise(
        (point[2], point[0], point[1]),
        seed + 211,
        base_frequency=1.8,
        octaves=4,
    )
    moisture = max(0.0, min(1.0, moisture))

    sea_level = -0.10
    is_ocean = continent < sea_level
    is_rare_island = (
        is_ocean
        and continent > sea_level - 0.28
        and island_score > 0.42
        and abs_lat < 72.0
    )
    if is_ocean and not is_rare_island:
        ocean_depth = int(round(-120 - (sea_level - continent) * 2400))
        return TerrainSample(
            biome="ocean",
            elevation_m=ocean_depth,
            continent_score=continent,
            moisture=moisture,
        )

    mountain_score = 1.0 - abs(
        _smooth_noise(
            (point[1], point[2], point[0]),
            seed + 307,
            base_frequency=3.2,
            octaves=4,
        )
    )
    basin_score = abs(
        _smooth_noise(
            (point[0] + 0.13, point[1] - 0.07, point[2] + 0.05),
            seed + 331,
            base_frequency=7.0,
            octaves=2,
        )
    )
    river_score = abs(
        _smooth_noise(
            (point[2] - 0.05, point[0] + 0.03, point[1]),
            seed + 401,
            base_frequency=8.0,
            octaves=2,
        )
    )

    land_height = max(0.0, continent - sea_level)
    elevation = int(round(35 + land_height * 1700 + (mountain_score**4) * 3100))
    has_mountain = mountain_score > 0.94 and elevation > 1250 and abs_lat < 82.0
    has_lake = (
        not has_mountain
        and moisture > 0.55
        and basin_score < 0.13
        and elevation < 1100
        and abs_lat < 70.0
    )
    has_river = (
        not has_lake
        and river_score < 0.055
        and moisture > 0.34
        and elevation > 80
        and abs_lat < 78.0
    )

    features = 0
    if is_rare_island:
        features |= FEATURE_ISLAND
    if has_mountain:
        features |= FEATURE_MOUNTAIN
    if has_lake:
        features |= FEATURE_LAKE
    if has_river:
        features |= FEATURE_RIVER

    if has_lake:
        biome = "lake"
        elevation = max(0, min(elevation, 220))
    elif has_mountain:
        biome = "mountain"
    else:
        biome = _land_biome(latitude, moisture)

    river_drop = round(8.0 + mountain_score * 70.0, 1) if has_river else 0.0
    return TerrainSample(
        biome=biome,
        elevation_m=elevation,
        features=features,
        river_drop_m=river_drop,
        continent_score=continent,
        moisture=moisture,
    )


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


def _land_biome(latitude: float, moisture: float) -> str:
    abs_lat = abs(latitude)
    if abs_lat >= 75:
        return "polar"
    if abs_lat >= 62:
        return "tundra"
    if abs_lat >= 48:
        return "boreal" if moisture >= 0.35 else "tundra"
    if abs_lat >= 32:
        if moisture < 0.22:
            return "desert"
        if moisture < 0.45:
            return "steppe"
        return "temperate"
    if abs_lat >= 16:
        if moisture < 0.25:
            return "desert"
        if moisture < 0.50:
            return "steppe"
        return "tropical"
    return "tropical" if moisture >= 0.35 else "desert"


def _smooth_noise(
    point: Vec3,
    salt: int,
    *,
    base_frequency: float,
    octaves: int,
) -> float:
    value = 0.0
    amplitude = 1.0
    total_amplitude = 0.0
    frequency = base_frequency
    for octave in range(octaves):
        value += amplitude * _wave_noise(point, salt + octave * 37, frequency)
        total_amplitude += amplitude
        amplitude *= 0.5
        frequency *= 1.9
    return value / total_amplitude


def _wave_noise(point: Vec3, salt: int, frequency: float) -> float:
    axes = (
        (0.87, 0.31, 0.38),
        (-0.22, 0.91, 0.35),
        (0.43, -0.57, 0.70),
        (-0.68, -0.18, 0.71),
    )
    phase = salt * 0.173
    value = 0.0
    for index, axis in enumerate(axes):
        dot = point[0] * axis[0] + point[1] * axis[1] + point[2] * axis[2]
        angle = dot * frequency * (index + 1.3) + phase + index * 1.917
        value += sin(angle) * 0.72 + cos(angle * 0.63 + phase * 0.31) * 0.28
    return value / len(axes)


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
