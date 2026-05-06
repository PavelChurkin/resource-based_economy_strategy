"""Chunked ISEA3H-style hex sphere mesh and indexing helpers.

Issue #7 asks for a very large spherical planet: one tenth of Earth's radius,
with future gameplay targeting roughly 10 metre hexes. That target implies
billions of logical cells, so this module separates:

- lightweight logical ISEA3H grid metadata and stable cell ids,
- small procedural render meshes that can be rotated and zoomed by a client,
- chunk and spatial-index helpers for loading only the cells near a camera,
- event payloads that reference cell ids instead of sending polygons.

The render mesh is the dual of a subdivided icosahedron. It produces the
expected twelve pentagons and a hex-dominant spherical mesh, while the
``Isea3hGridSpec`` keeps the aperture-3 hierarchy needed by the simulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import (
    acos,
    asin,
    atan2,
    ceil,
    cos,
    degrees,
    floor,
    log,
    pi,
    sin,
    sqrt,
)
from typing import Iterable, Mapping

from .planet import Terrain


Vec3 = tuple[float, float, float]

EARTH_RADIUS_M = 6_371_000.0
DEFAULT_TENTH_EARTH_RADIUS_M = EARTH_RADIUS_M / 10.0
DEFAULT_MEMORY_BUDGET_BYTES = 1_000_000_000

_CELL_ID_RESOLUTION_FACTOR = 1_000_000_000_000
_CELL_ID_FACE_FACTOR = 10_000_000_000


@dataclass(frozen=True)
class Isea3hGridSpec:
    """Logical aperture-3 hexagonal grid specification.

    ``logical_cell_count`` follows the usual icosahedral hex-grid count:
    twelve pentagons plus mostly hexagonal cells, with aperture 3 increasing
    cell count by a factor of three per resolution level.
    """

    resolution: int
    planet_radius_m: float = DEFAULT_TENTH_EARTH_RADIUS_M
    aperture: int = 3

    def __post_init__(self) -> None:
        if self.resolution < 0:
            raise ValueError("resolution must be non-negative")
        if self.planet_radius_m <= 0:
            raise ValueError("planet_radius_m must be positive")
        if self.aperture != 3:
            raise ValueError("this module models ISEA3H, so aperture must be 3")

    @property
    def logical_cell_count(self) -> int:
        return 10 * (self.aperture**self.resolution) + 2

    @property
    def surface_area_m2(self) -> float:
        return 4 * pi * self.planet_radius_m * self.planet_radius_m

    @property
    def average_cell_area_m2(self) -> float:
        return self.surface_area_m2 / self.logical_cell_count

    @property
    def average_hex_edge_m(self) -> float:
        """Approximate regular-hex edge length for the average cell area."""

        return sqrt((2 * self.average_cell_area_m2) / (3 * sqrt(3)))

    @classmethod
    def for_target_hex_edge_m(
        cls,
        target_hex_edge_m: float,
        planet_radius_m: float = DEFAULT_TENTH_EARTH_RADIUS_M,
    ) -> Isea3hGridSpec:
        if target_hex_edge_m <= 0:
            raise ValueError("target_hex_edge_m must be positive")
        target_area = 3 * sqrt(3) / 2 * target_hex_edge_m * target_hex_edge_m
        required_cells = 4 * pi * planet_radius_m * planet_radius_m / target_area
        resolution = max(0, ceil(log(max((required_cells - 2) / 10, 1), 3)))
        return cls(resolution=resolution, planet_radius_m=planet_radius_m)

    def estimated_state_bytes(self, bytes_per_cell: int) -> int:
        if bytes_per_cell <= 0:
            raise ValueError("bytes_per_cell must be positive")
        return self.logical_cell_count * bytes_per_cell

    def max_loaded_cells(
        self,
        memory_budget_bytes: int = DEFAULT_MEMORY_BUDGET_BYTES,
        bytes_per_cell: int = 32,
    ) -> int:
        if memory_budget_bytes <= 0:
            raise ValueError("memory_budget_bytes must be positive")
        if bytes_per_cell <= 0:
            raise ValueError("bytes_per_cell must be positive")
        return memory_budget_bytes // bytes_per_cell

    def requires_chunk_streaming(
        self,
        memory_budget_bytes: int = DEFAULT_MEMORY_BUDGET_BYTES,
        bytes_per_cell: int = 32,
    ) -> bool:
        return self.logical_cell_count > self.max_loaded_cells(
            memory_budget_bytes=memory_budget_bytes,
            bytes_per_cell=bytes_per_cell,
        )


@dataclass(frozen=True)
class HexSphereCell:
    """Renderable cell on the sphere.

    The boundary stores unit-sphere vertices. Clients scale those points by
    planet radius and by elevation when building a GPU mesh.
    """

    id: int
    center: Vec3
    boundary: tuple[Vec3, ...]
    face: int
    chunk_id: str
    terrain: Terrain
    latitude: float
    longitude: float

    @property
    def is_pentagon(self) -> bool:
        return len(self.boundary) == 5

    def to_render_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "token": f"#{self.id}",
            "center": _round_vec(self.center),
            "boundary": [_round_vec(vertex) for vertex in self.boundary],
            "face": self.face,
            "chunk": self.chunk_id,
            "shape": "pentagon" if self.is_pentagon else "hexagon",
            "lat": round(self.latitude, 4),
            "lon": round(self.longitude, 4),
            "biome": self.terrain.biome,
            "elevationM": self.terrain.elevation_m,
            "hasRiver": self.terrain.has_river,
        }


@dataclass(frozen=True)
class HexSphereChunk:
    id: str
    face: int
    center: Vec3
    angular_radius_rad: float
    cell_ids: tuple[int, ...]

    def to_render_dict(self, cells_by_id: Mapping[int, HexSphereCell]) -> dict[str, object]:
        return {
            "id": self.id,
            "face": self.face,
            "center": _round_vec(self.center),
            "angularRadiusRad": round(self.angular_radius_rad, 6),
            "cells": [cells_by_id[cell_id].to_render_dict() for cell_id in self.cell_ids],
        }


@dataclass(frozen=True)
class HexSphereMesh:
    spec: Isea3hGridSpec
    frequency: int
    cells: tuple[HexSphereCell, ...]
    chunks: tuple[HexSphereChunk, ...]

    @property
    def cells_by_id(self) -> dict[int, HexSphereCell]:
        return {cell.id: cell for cell in self.cells}

    def estimated_cell_state_bytes(self, bytes_per_cell: int = 96) -> int:
        if bytes_per_cell <= 0:
            raise ValueError("bytes_per_cell must be positive")
        return len(self.cells) * bytes_per_cell

    def to_render_payload(self) -> dict[str, object]:
        cells_by_id = self.cells_by_id
        return {
            "grid": {
                "projection": "ISEA",
                "aperture": self.spec.aperture,
                "resolution": self.spec.resolution,
                "logicalCellCount": self.spec.logical_cell_count,
                "renderCellCount": len(self.cells),
                "renderFrequency": self.frequency,
                "planetRadiusM": self.spec.planet_radius_m,
                "averageHexEdgeM": round(self.spec.average_hex_edge_m, 3),
            },
            "chunks": [
                chunk.to_render_dict(cells_by_id) for chunk in sorted(
                    self.chunks,
                    key=lambda chunk: chunk.id,
                )
            ],
        }


@dataclass(frozen=True)
class CellEvent:
    """Network event that references one cell instead of sending geometry."""

    tick: int
    actor_id: str
    cell_id: int
    action: str
    payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.tick < 0:
            raise ValueError("tick must be non-negative")
        if not self.actor_id:
            raise ValueError("actor_id must be non-empty")
        if self.cell_id < 0:
            raise ValueError("cell_id must be non-negative")
        if not self.action:
            raise ValueError("action must be non-empty")

    def to_wire(self) -> dict[str, object]:
        return {
            "tick": self.tick,
            "actor": self.actor_id,
            "cell": f"#{self.cell_id}",
            "action": self.action,
            "payload": dict(self.payload),
        }


class CellSpatialIndex:
    """Chunk-first spatial index for camera and gameplay proximity queries."""

    def __init__(self, mesh: HexSphereMesh) -> None:
        self.mesh = mesh
        cells_by_id = mesh.cells_by_id
        self._chunk_cells = {
            chunk.id: tuple(cells_by_id[cell_id] for cell_id in chunk.cell_ids)
            for chunk in mesh.chunks
        }
        self.last_examined_chunk_count = 0
        self.last_examined_cell_count = 0

    def nearby_cells(
        self,
        direction: Vec3,
        angular_radius_rad: float,
        *,
        limit: int | None = None,
    ) -> list[HexSphereCell]:
        if angular_radius_rad < 0:
            raise ValueError("angular_radius_rad must be non-negative")
        if limit is not None and limit <= 0:
            raise ValueError("limit must be positive when provided")

        center = _normalize(direction)
        threshold = cos(angular_radius_rad)
        candidate_cells: list[HexSphereCell] = []
        candidate_chunks = 0
        for chunk in self.mesh.chunks:
            if _angle_between(center, chunk.center) <= (
                angular_radius_rad + chunk.angular_radius_rad
            ):
                candidate_chunks += 1
                candidate_cells.extend(self._chunk_cells[chunk.id])

        self.last_examined_chunk_count = candidate_chunks
        self.last_examined_cell_count = len(candidate_cells)
        result = [
            cell for cell in candidate_cells if _dot(center, cell.center) >= threshold
        ]
        result.sort(key=lambda cell: _dot(center, cell.center), reverse=True)
        if limit is not None:
            return result[:limit]
        return result


def render_frequency_for_resolution(resolution: int) -> int:
    """Return the exact geodesic dual frequency for even ISEA3H levels.

    The geodesic dual has ``10 * frequency**2 + 2`` cells. Even ISEA3H
    resolutions therefore map exactly when ``frequency = 3 ** (resolution / 2)``.
    Odd aperture-3 levels need a rotated Goldberg transform; the logical spec
    still supports them, while this lightweight renderer currently uses even
    levels for exact cell counts.
    """

    if resolution < 0:
        raise ValueError("resolution must be non-negative")
    if resolution % 2:
        raise ValueError(
            "render mesh has exact counts for even ISEA3H resolutions only"
        )
    return 3 ** (resolution // 2)


def build_hex_sphere_lod_payload(
    *,
    grid_resolutions: Iterable[int] = (2, 4, 6),
    planet_radius_m: float = DEFAULT_TENTH_EARTH_RADIUS_M,
    zoom_thresholds: Iterable[float] | None = None,
) -> dict[str, object]:
    """Build a multi-resolution payload for zoom-driven LOD rendering.

    The viewer holds several meshes at once and switches between them as the
    camera zooms. Each level uses an even ISEA3H resolution with an exact dual
    cell count. The first level is the lowest density (drawn far from the
    planet), the last is the highest density (drawn when zoomed in).
    """

    levels = sorted({int(resolution) for resolution in grid_resolutions})
    if not levels:
        raise ValueError("grid_resolutions must contain at least one resolution")

    meshes = [
        build_hex_sphere_mesh(
            grid_resolution=resolution,
            planet_radius_m=planet_radius_m,
        )
        for resolution in levels
    ]

    if zoom_thresholds is None:
        thresholds: tuple[float, ...] = tuple(
            round(1.0 + index * 0.6, 6) for index in range(len(levels) - 1)
        )
    else:
        thresholds = tuple(float(value) for value in zoom_thresholds)
        if len(thresholds) != len(levels) - 1:
            raise ValueError(
                "zoom_thresholds must have one fewer entry than grid_resolutions"
            )

    return {
        "kind": "lod",
        "planetRadiusM": planet_radius_m,
        "zoomThresholds": list(thresholds),
        "levels": [mesh.to_render_payload() for mesh in meshes],
    }


def build_hex_sphere_mesh(
    *,
    frequency: int | None = None,
    grid_resolution: int = 4,
    planet_radius_m: float = DEFAULT_TENTH_EARTH_RADIUS_M,
) -> HexSphereMesh:
    """Build a chunked procedural hex/pent mesh on a unit sphere.

    ``frequency`` controls render density. When omitted, an even ISEA3H
    ``grid_resolution`` is mapped to an exact geodesic dual frequency.
    """

    if frequency is None:
        frequency = render_frequency_for_resolution(grid_resolution)
    if frequency < 1:
        raise ValueError("frequency must be positive")

    spec = Isea3hGridSpec(
        resolution=grid_resolution,
        planet_radius_m=planet_radius_m,
    )
    ico_vertices, ico_faces = _icosahedron()
    face_centers = tuple(
        _normalize(_add3(ico_vertices[a], ico_vertices[b], ico_vertices[c]))
        for a, b, c in ico_faces
    )
    vertices, triangles = _subdivide_icosahedron(ico_vertices, ico_faces, frequency)
    triangle_centers = tuple(
        _normalize(_add3(vertices[a], vertices[b], vertices[c]))
        for a, b, c in triangles
    )

    incident: dict[int, list[int]] = {index: [] for index in range(len(vertices))}
    for triangle_index, triangle in enumerate(triangles):
        for vertex_index in triangle:
            incident[vertex_index].append(triangle_index)

    raw_cells: list[tuple[Vec3, tuple[Vec3, ...], int, Terrain, float, float]] = []
    for vertex_index, triangle_indices in incident.items():
        center = vertices[vertex_index]
        boundary = _sort_boundary(center, (triangle_centers[i] for i in triangle_indices))
        if len(boundary) not in (5, 6):
            continue
        face = _dominant_face(center, face_centers)
        latitude, longitude = _lat_lon(center)
        terrain = _terrain_for(center, latitude, vertex_index)
        raw_cells.append((center, boundary, face, terrain, latitude, longitude))

    raw_cells.sort(key=lambda item: (item[2], round(item[0][2], 12), round(item[0][1], 12)))
    face_local_counts: dict[int, int] = {}
    cells: list[HexSphereCell] = []
    for center, boundary, face, terrain, latitude, longitude in raw_cells:
        local = face_local_counts.get(face, 0)
        face_local_counts[face] = local + 1
        cell_id = _encode_cell_id(spec.resolution, face, local)
        chunk_id = _chunk_id(spec.resolution, face)
        cells.append(
            HexSphereCell(
                id=cell_id,
                center=center,
                boundary=boundary,
                face=face,
                chunk_id=chunk_id,
                terrain=terrain,
                latitude=latitude,
                longitude=longitude,
            )
        )

    chunks = _build_chunks(cells, spec.resolution)
    return HexSphereMesh(
        spec=spec,
        frequency=frequency,
        cells=tuple(cells),
        chunks=tuple(chunks),
    )


def _icosahedron() -> tuple[tuple[Vec3, ...], tuple[tuple[int, int, int], ...]]:
    phi = (1 + sqrt(5)) / 2
    vertices = tuple(
        _normalize(vertex)
        for vertex in (
            (-1, phi, 0),
            (1, phi, 0),
            (-1, -phi, 0),
            (1, -phi, 0),
            (0, -1, phi),
            (0, 1, phi),
            (0, -1, -phi),
            (0, 1, -phi),
            (phi, 0, -1),
            (phi, 0, 1),
            (-phi, 0, -1),
            (-phi, 0, 1),
        )
    )
    faces = (
        (0, 11, 5),
        (0, 5, 1),
        (0, 1, 7),
        (0, 7, 10),
        (0, 10, 11),
        (1, 5, 9),
        (5, 11, 4),
        (11, 10, 2),
        (10, 7, 6),
        (7, 1, 8),
        (3, 9, 4),
        (3, 4, 2),
        (3, 2, 6),
        (3, 6, 8),
        (3, 8, 9),
        (4, 9, 5),
        (2, 4, 11),
        (6, 2, 10),
        (8, 6, 7),
        (9, 8, 1),
    )
    return vertices, faces


def _subdivide_icosahedron(
    ico_vertices: tuple[Vec3, ...],
    ico_faces: tuple[tuple[int, int, int], ...],
    frequency: int,
) -> tuple[tuple[Vec3, ...], tuple[tuple[int, int, int], ...]]:
    vertices: list[Vec3] = []
    vertex_by_position: dict[tuple[float, float, float], int] = {}
    triangles: list[tuple[int, int, int]] = []

    def get_vertex(point: Vec3) -> int:
        unit = _normalize(point)
        key = _round_vec(unit, places=12)
        index = vertex_by_position.get(key)
        if index is not None:
            return index
        index = len(vertices)
        vertices.append(unit)
        vertex_by_position[key] = index
        return index

    for a_index, b_index, c_index in ico_faces:
        a = ico_vertices[a_index]
        b = ico_vertices[b_index]
        c = ico_vertices[c_index]
        local: dict[tuple[int, int], int] = {}
        for i in range(frequency + 1):
            for j in range(frequency + 1 - i):
                k = frequency - i - j
                point = (
                    (a[0] * k + b[0] * i + c[0] * j) / frequency,
                    (a[1] * k + b[1] * i + c[1] * j) / frequency,
                    (a[2] * k + b[2] * i + c[2] * j) / frequency,
                )
                local[(i, j)] = get_vertex(point)

        for i in range(frequency):
            for j in range(frequency - i):
                triangles.append((local[(i, j)], local[(i + 1, j)], local[(i, j + 1)]))
                if j < frequency - i - 1:
                    triangles.append(
                        (
                            local[(i + 1, j)],
                            local[(i + 1, j + 1)],
                            local[(i, j + 1)],
                        )
                    )

    return tuple(vertices), tuple(triangles)


def _sort_boundary(center: Vec3, boundary: Iterable[Vec3]) -> tuple[Vec3, ...]:
    points = tuple(boundary)
    if not points:
        return ()
    u, v = _tangent_basis(center)
    return tuple(
        sorted(
            points,
            key=lambda point: atan2(_dot(point, v), _dot(point, u)),
        )
    )


def _tangent_basis(normal: Vec3) -> tuple[Vec3, Vec3]:
    axis = (0.0, 0.0, 1.0)
    if abs(_dot(normal, axis)) > 0.9:
        axis = (0.0, 1.0, 0.0)
    u = _normalize(_cross(axis, normal))
    v = _normalize(_cross(normal, u))
    return u, v


def _build_chunks(cells: list[HexSphereCell], resolution: int) -> list[HexSphereChunk]:
    cells_by_chunk: dict[str, list[HexSphereCell]] = {}
    for cell in cells:
        cells_by_chunk.setdefault(cell.chunk_id, []).append(cell)

    chunks: list[HexSphereChunk] = []
    for chunk_id, chunk_cells in sorted(cells_by_chunk.items()):
        center = _normalize(_sum_vec(cell.center for cell in chunk_cells))
        angular_radius = max(_angle_between(center, cell.center) for cell in chunk_cells)
        face = int(chunk_id.rsplit("f", maxsplit=1)[1])
        chunks.append(
            HexSphereChunk(
                id=chunk_id,
                face=face,
                center=center,
                angular_radius_rad=angular_radius,
                cell_ids=tuple(cell.id for cell in chunk_cells),
            )
        )
    expected_chunks = { _chunk_id(resolution, face) for face in range(20) }
    missing = expected_chunks.difference(cells_by_chunk)
    for chunk_id in sorted(missing):
        face = int(chunk_id.rsplit("f", maxsplit=1)[1])
        chunks.append(
            HexSphereChunk(
                id=chunk_id,
                face=face,
                center=(0.0, 0.0, 1.0),
                angular_radius_rad=0.0,
                cell_ids=(),
            )
        )
    chunks.sort(key=lambda chunk: chunk.id)
    return chunks


def _terrain_for(center: Vec3, latitude: float, salt: int) -> Terrain:
    noise = _noise(center, salt)
    if noise < 0.36:
        return Terrain(
            elevation_m=round(-250 + noise * 500, 1),
            river_drop_m=0.0,
            biome="ocean",
            has_river=False,
        )

    biome = _biome_for_latitude(latitude)
    elevation_noise = _noise((center[1], center[2], center[0]), salt + 17)
    elevation = round(elevation_noise * 2200.0, 1)
    has_river = biome not in {"polar", "desert"} and _noise(center, salt + 31) > 0.72
    river_drop = round(_noise(center, salt + 53) * 80.0, 1) if has_river else 0.0
    return Terrain(
        elevation_m=elevation,
        river_drop_m=river_drop,
        biome=biome,
        has_river=has_river,
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


def _noise(center: Vec3, salt: int) -> float:
    value = sin(
        center[0] * 12.9898
        + center[1] * 78.233
        + center[2] * 37.719
        + salt * 0.1113
    ) * 43_758.5453
    return value - floor(value)


def _dominant_face(center: Vec3, face_centers: tuple[Vec3, ...]) -> int:
    return max(range(len(face_centers)), key=lambda index: _dot(center, face_centers[index]))


def _encode_cell_id(resolution: int, face: int, local_index: int) -> int:
    return (
        resolution * _CELL_ID_RESOLUTION_FACTOR
        + face * _CELL_ID_FACE_FACTOR
        + local_index
    )


def _chunk_id(resolution: int, face: int) -> str:
    return f"r{resolution:02d}:f{face:02d}"


def _lat_lon(center: Vec3) -> tuple[float, float]:
    latitude = degrees(asin(max(-1.0, min(1.0, center[2]))))
    longitude = degrees(atan2(center[1], center[0]))
    return latitude, longitude


def _round_vec(vector: Vec3, places: int = 6) -> tuple[float, float, float]:
    return (round(vector[0], places), round(vector[1], places), round(vector[2], places))


def _normalize(vector: Vec3) -> Vec3:
    length = sqrt(_dot(vector, vector))
    if length == 0:
        raise ValueError("cannot normalize zero vector")
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _add3(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    return (a[0] + b[0] + c[0], a[1] + b[1] + c[1], a[2] + b[2] + c[2])


def _sum_vec(vectors: Iterable[Vec3]) -> Vec3:
    x = y = z = 0.0
    for vector in vectors:
        x += vector[0]
        y += vector[1]
        z += vector[2]
    return (x, y, z)


def _angle_between(a: Vec3, b: Vec3) -> float:
    return acos(max(-1.0, min(1.0, _dot(a, b))))
