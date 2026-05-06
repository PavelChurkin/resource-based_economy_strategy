"""Game1 — planetary scaffolding for the resource-only strategy simulation.

This package focuses on the aspects emphasised in issue #3:

- a polygonal-sphere planet with latitude-aware climate,
- cyclone / anticyclone weather influencing solar, wind and water yields,
- terrain elevation that gates hydropower potential,
- a tech tree compatible with the external ``techno2.json`` schema,
- a time controller that supports pause, speed and fast-forward extrapolation
  for skipped weeks, months and years.

The modules are intentionally dependency-free standard-library Python so the
core can run on the modest server profile mentioned in the issue.
"""

from .planet import Planet, PlanetTile, Terrain, build_demo_planet
from .climate import Climate, PressureSystem, TileWeather
from .hex_sphere import (
    CellEvent,
    CellSpatialIndex,
    HexSphereCell,
    HexSphereChunk,
    HexSphereMesh,
    Isea3hGridSpec,
    build_hex_sphere_lod_payload,
    build_hex_sphere_mesh,
)
from .tech_tree import Technology, TechTree, load_tech_tree, parse_tech_tree
from .time_control import TimeController, TimeMode

__all__ = [
    "Planet",
    "PlanetTile",
    "Terrain",
    "build_demo_planet",
    "Climate",
    "PressureSystem",
    "TileWeather",
    "CellEvent",
    "CellSpatialIndex",
    "HexSphereCell",
    "HexSphereChunk",
    "HexSphereMesh",
    "Isea3hGridSpec",
    "build_hex_sphere_lod_payload",
    "build_hex_sphere_mesh",
    "Technology",
    "TechTree",
    "load_tech_tree",
    "parse_tech_tree",
    "TimeController",
    "TimeMode",
]
