import math
import unittest

from game1.hex_sphere import (
    DEFAULT_TENTH_EARTH_RADIUS_M,
    CellEvent,
    CellSpatialIndex,
    Isea3hGridSpec,
    build_hex_sphere_lod_payload,
    build_hex_sphere_mesh,
)
from game1.hex_sphere_viewer import (
    render_lod_viewer_html,
    render_viewer_html,
)


class Isea3hGridSpecTests(unittest.TestCase):
    def test_aperture_three_logical_cell_counts(self) -> None:
        self.assertEqual(Isea3hGridSpec(resolution=0).logical_cell_count, 12)
        self.assertEqual(Isea3hGridSpec(resolution=1).logical_cell_count, 32)
        self.assertEqual(Isea3hGridSpec(resolution=2).logical_cell_count, 92)
        self.assertEqual(Isea3hGridSpec(resolution=3).logical_cell_count, 272)

    def test_ten_meter_planet_requires_streamed_chunks(self) -> None:
        spec = Isea3hGridSpec.for_target_hex_edge_m(
            target_hex_edge_m=10.0,
            planet_radius_m=DEFAULT_TENTH_EARTH_RADIUS_M,
        )

        self.assertLessEqual(spec.average_hex_edge_m, 10.0)
        self.assertGreater(spec.logical_cell_count, 10_000_000_000)
        self.assertTrue(
            spec.requires_chunk_streaming(
                memory_budget_bytes=1_000_000_000,
                bytes_per_cell=32,
            )
        )


class HexSphereMeshTests(unittest.TestCase):
    def test_mesh_is_hex_dominant_and_chunked(self) -> None:
        mesh = build_hex_sphere_mesh(frequency=3, grid_resolution=2)

        self.assertEqual(len(mesh.cells), 92)
        self.assertEqual(sum(cell.is_pentagon for cell in mesh.cells), 12)
        self.assertTrue(all(len(cell.boundary) in (5, 6) for cell in mesh.cells))
        self.assertGreaterEqual(len(mesh.chunks), 20)
        self.assertLess(mesh.estimated_cell_state_bytes(), 1_000_000_000)

    def test_spatial_index_limits_nearby_search_to_candidate_chunks(self) -> None:
        mesh = build_hex_sphere_mesh(frequency=5, grid_resolution=2)
        index = CellSpatialIndex(mesh)
        sample = next(cell for cell in mesh.cells if not cell.is_pentagon)

        nearby = index.nearby_cells(sample.center, angular_radius_rad=math.radians(8))

        self.assertIn(sample.id, {cell.id for cell in nearby})
        self.assertLess(index.last_examined_cell_count, len(mesh.cells))

    def test_render_payload_uses_chunks_and_stable_cell_ids(self) -> None:
        mesh = build_hex_sphere_mesh(frequency=3, grid_resolution=2)
        payload = mesh.to_render_payload()

        self.assertEqual(payload["grid"]["aperture"], 3)
        self.assertEqual(payload["grid"]["logicalCellCount"], 92)
        self.assertTrue(payload["chunks"])
        first_chunk = payload["chunks"][0]
        first_cell = first_chunk["cells"][0]
        self.assertIn("id", first_cell)
        self.assertIn("center", first_cell)
        self.assertIn("boundary", first_cell)

    def test_cell_event_wire_payload_does_not_send_polygons(self) -> None:
        mesh = build_hex_sphere_mesh(frequency=3, grid_resolution=2)
        event = CellEvent(
            tick=12,
            actor_id="player-a",
            cell_id=mesh.cells[0].id,
            action="start_build",
            payload={"building": "solar_panel"},
        )

        wire = event.to_wire()

        self.assertEqual(wire["cell"], f"#{mesh.cells[0].id}")
        self.assertNotIn("boundary", wire)
        self.assertNotIn("vertices", wire)


class HexSphereLodPayloadTests(unittest.TestCase):
    def test_lod_payload_orders_resolutions_low_to_high(self) -> None:
        payload = build_hex_sphere_lod_payload(grid_resolutions=(4, 2))

        self.assertEqual(payload["kind"], "lod")
        self.assertEqual(len(payload["levels"]), 2)
        self.assertEqual(payload["levels"][0]["grid"]["resolution"], 2)
        self.assertEqual(payload["levels"][1]["grid"]["resolution"], 4)
        self.assertEqual(len(payload["zoomThresholds"]), 1)

    def test_lod_payload_default_levels_grow(self) -> None:
        payload = build_hex_sphere_lod_payload(grid_resolutions=(2, 4, 6))

        cells_per_level = [
            level["grid"]["renderCellCount"] for level in payload["levels"]
        ]
        self.assertEqual(cells_per_level, [92, 812, 7292])
        self.assertEqual(payload["zoomThresholds"], [1.0, 1.6])

    def test_lod_payload_validates_thresholds_length(self) -> None:
        with self.assertRaises(ValueError):
            build_hex_sphere_lod_payload(
                grid_resolutions=(2, 4),
                zoom_thresholds=(1.0, 2.0),
            )

    def test_lod_payload_requires_resolutions(self) -> None:
        with self.assertRaises(ValueError):
            build_hex_sphere_lod_payload(grid_resolutions=())


class HexSphereViewerHtmlTests(unittest.TestCase):
    def test_legacy_render_viewer_wraps_single_level_payload(self) -> None:
        mesh = build_hex_sphere_mesh(frequency=3, grid_resolution=2)

        html = render_viewer_html(mesh)

        self.assertIn('"kind":"lod"', html)
        self.assertIn('"renderCellCount":92', html)
        for letter in ("W", "A", "S", "D"):
            self.assertIn(f"<kbd>{letter}</kbd>", html)

    def test_lod_viewer_html_contains_keyboard_shortcut_hints(self) -> None:
        payload = build_hex_sphere_lod_payload(grid_resolutions=(2, 4))

        html = render_lod_viewer_html(payload)

        for letter in ("W", "A", "S", "D"):
            self.assertIn(f"<kbd>{letter}</kbd>", html)
        self.assertIn("requestAnimationFrame", html)
        self.assertIn("zoomThresholds", html)

    def test_render_lod_viewer_rejects_non_lod_payload(self) -> None:
        with self.assertRaises(ValueError):
            render_lod_viewer_html({"kind": "single", "levels": []})


if __name__ == "__main__":
    unittest.main()
