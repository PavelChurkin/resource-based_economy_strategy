"""Polygonal-sphere planet model for the resource-based strategy.

The planet is approximated as a grid of latitude/longitude tiles. Each tile
carries terrain information (elevation, biome, river drop) so other modules
can derive resource yields, hydropower potential and climate baselines.

The grid is intentionally coarse — issue #3 suggests a 1:1000 (or smaller)
planet — but the data layout is chosen so that an icosphere or higher
resolution tessellation can replace it without changing the public API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, radians, pi
from typing import Iterable, Iterator


BIOMES = (
    "polar",
    "tundra",
    "boreal",
    "temperate",
    "steppe",
    "desert",
    "tropical",
    "ocean",
)


@dataclass(frozen=True)
class Terrain:
    """Static terrain attributes for a tile.

    ``elevation_m`` and ``river_drop_m`` together give the head used to
    estimate hydropower potential. ``biome`` controls baseline temperature and
    resource availability.
    """

    elevation_m: float
    river_drop_m: float
    biome: str
    has_river: bool

    def __post_init__(self) -> None:
        if self.biome not in BIOMES:
            raise ValueError(
                f"unknown biome {self.biome!r}; expected one of {BIOMES}"
            )
        if self.elevation_m < -500.0:
            raise ValueError("elevation_m must be >= -500")
        if self.river_drop_m < 0.0:
            raise ValueError("river_drop_m must be >= 0")
        if self.river_drop_m > 0 and not self.has_river:
            raise ValueError("river_drop_m > 0 requires has_river=True")


@dataclass
class PlanetTile:
    """A single tile of the polygonal sphere."""

    latitude: float
    longitude: float
    terrain: Terrain
    resources: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError("latitude must be within [-90, 90]")
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError("longitude must be within [-180, 180]")

    def hydropower_potential_kw(self) -> float:
        """Return rough hydropower potential for the tile in kilowatts.

        Uses ``P = rho * g * Q * h * efficiency`` with a fixed flow estimate of
        ``Q = 1 m^3/s`` per metre of elevation drop and 80% efficiency. This
        is enough for relative comparisons between tiles; absolute calibration
        is deferred to later versions.
        """

        if not self.terrain.has_river:
            return 0.0
        rho = 1000.0  # kg/m^3
        g = 9.81  # m/s^2
        flow_m3_s = max(self.terrain.river_drop_m, 1.0)
        head_m = self.terrain.river_drop_m
        efficiency = 0.8
        watts = rho * g * flow_m3_s * head_m * efficiency
        return watts / 1000.0

    def solar_baseline(self) -> float:
        """Tile's baseline solar factor before weather effects (0..1)."""

        # Cosine-of-latitude approximation of insolation.
        return max(0.0, cos(radians(self.latitude)))

    def wind_baseline(self) -> float:
        """Tile's baseline wind factor before weather effects (0..1)."""

        # Highland and ocean tiles see stronger prevailing winds.
        base = 0.4
        if self.terrain.biome == "ocean":
            base = 0.7
        elif self.terrain.elevation_m > 800:
            base = 0.6
        return base


@dataclass
class Planet:
    """A simple lat/lon grid planet."""

    tiles: list[PlanetTile]
    radius_km: float = 6371.0 / 1000.0  # default 1:1000 scale of Earth

    def __iter__(self) -> Iterator[PlanetTile]:
        return iter(self.tiles)

    def __len__(self) -> int:
        return len(self.tiles)

    def find(self, latitude: float, longitude: float) -> PlanetTile:
        for tile in self.tiles:
            if (
                abs(tile.latitude - latitude) < 1e-6
                and abs(tile.longitude - longitude) < 1e-6
            ):
                return tile
        raise KeyError(f"no tile at ({latitude}, {longitude})")

    def surface_area_km2(self) -> float:
        return 4 * pi * self.radius_km * self.radius_km

    def tiles_with_rivers(self) -> list[PlanetTile]:
        return [tile for tile in self.tiles if tile.terrain.has_river]

    def best_hydropower_tiles(self, limit: int = 3) -> list[PlanetTile]:
        ranked = sorted(
            self.tiles_with_rivers(),
            key=lambda t: t.hydropower_potential_kw(),
            reverse=True,
        )
        return ranked[:limit]


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


def build_demo_planet(
    latitude_step: float = 30.0,
    longitude_step: float = 60.0,
    radius_km: float = 6.371,
    seed: int = 42,
) -> Planet:
    """Build a deterministic demo planet for examples and tests.

    The grid is coarse but exercises every part of the pipeline: cold polar
    tiles, temperate tiles with rivers and a hot equatorial belt. ``seed``
    seeds a small linear-congruential generator so the output is stable
    without requiring ``random``.
    """

    if latitude_step <= 0 or longitude_step <= 0:
        raise ValueError("steps must be positive")

    state = seed & 0xFFFFFFFF

    def next_unit() -> float:
        nonlocal state
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        return state / 0x7FFFFFFF

    tiles: list[PlanetTile] = []
    lat = -90.0
    while lat <= 90.0 + 1e-9:
        lon = -180.0
        while lon < 180.0 - 1e-9:
            biome = _biome_for_latitude(lat)
            elevation = round(next_unit() * 1500.0, 1)
            has_river = next_unit() < 0.4 and biome not in {"polar", "ocean"}
            river_drop = round(next_unit() * 60.0, 1) if has_river else 0.0
            terrain = Terrain(
                elevation_m=elevation,
                river_drop_m=river_drop,
                biome=biome,
                has_river=has_river,
            )
            resources: dict[str, float] = {}
            if biome in {"boreal", "temperate", "tropical"}:
                resources["wood"] = round(next_unit() * 100.0, 1)
            if biome in {"steppe", "temperate"}:
                resources["grain"] = round(next_unit() * 80.0, 1)
            if biome in {"tundra", "polar", "boreal"}:
                resources["iron_ore"] = round(next_unit() * 50.0, 1)
            if biome in {"desert", "tropical"}:
                resources["stone"] = round(next_unit() * 90.0, 1)
            tiles.append(
                PlanetTile(
                    latitude=lat,
                    longitude=lon,
                    terrain=terrain,
                    resources=resources,
                )
            )
            lon += longitude_step
        lat += latitude_step

    return Planet(tiles=tiles, radius_km=radius_km)


def iter_tiles_by_biome(planet: Planet, biome: str) -> Iterable[PlanetTile]:
    return (tile for tile in planet if tile.terrain.biome == biome)
