import math
import unittest

from game1.sphere_points import (
    BIOME_PALETTE,
    SpherePointPayload,
    build_sphere_point_level,
    build_sphere_point_payload,
    lat_lon_for_point,
)
from game1.webgl_planet_viewer import (
    render_webgl_viewer_html,
    write_webgl_viewer_html,
)


class SpherePointLevelTests(unittest.TestCase):
    def test_level_count_is_respected(self) -> None:
        level = build_sphere_point_level(count=64, seed=7)

        self.assertEqual(level.count, 64)
        self.assertEqual(len(level.positions), 64)
        self.assertEqual(len(level.biomes), 64)
        self.assertEqual(len(level.elevations_m), 64)

    def test_points_are_on_unit_sphere(self) -> None:
        level = build_sphere_point_level(count=200, seed=1)

        for x, y, z in level.positions:
            magnitude = math.sqrt(x * x + y * y + z * z)
            self.assertAlmostEqual(magnitude, 1.0, places=5)

    def test_seed_makes_output_deterministic(self) -> None:
        a = build_sphere_point_level(count=128, seed=42)
        b = build_sphere_point_level(count=128, seed=42)

        self.assertEqual(a.positions, b.positions)
        self.assertEqual(a.biomes, b.biomes)
        self.assertEqual(a.elevations_m, b.elevations_m)

    def test_biome_indices_match_palette(self) -> None:
        level = build_sphere_point_level(count=64, seed=5)
        max_index = len(BIOME_PALETTE) - 1
        for index in level.biomes:
            self.assertGreaterEqual(index, 0)
            self.assertLessEqual(index, max_index)

    def test_count_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            build_sphere_point_level(count=0)


class SpherePointPayloadTests(unittest.TestCase):
    def test_default_payload_has_three_levels_increasing(self) -> None:
        payload = build_sphere_point_payload()

        self.assertIsInstance(payload, SpherePointPayload)
        self.assertEqual(len(payload.levels), 3)
        counts = [level.count for level in payload.levels]
        self.assertEqual(counts, sorted(counts))
        self.assertEqual(len(payload.zoom_thresholds), len(payload.levels) - 1)

    def test_payload_orders_counts_low_to_high(self) -> None:
        payload = build_sphere_point_payload(counts=(20, 5, 80))

        counts = [level.count for level in payload.levels]
        self.assertEqual(counts, [5, 20, 80])

    def test_payload_validates_thresholds_length(self) -> None:
        with self.assertRaises(ValueError):
            build_sphere_point_payload(
                counts=(20, 80),
                zoom_thresholds=(1.0, 2.0),
            )

    def test_payload_requires_counts(self) -> None:
        with self.assertRaises(ValueError):
            build_sphere_point_payload(counts=())

    def test_target_must_be_at_least_largest_lod(self) -> None:
        with self.assertRaises(ValueError):
            build_sphere_point_payload(
                counts=(50, 200),
                target_logical_count=100,
            )

    def test_render_dict_contains_flat_arrays(self) -> None:
        payload = build_sphere_point_payload(counts=(20, 80))
        rendered = payload.to_render_payload()

        self.assertEqual(rendered["kind"], "sphere-points-lod")
        self.assertEqual(len(rendered["levels"]), 2)
        first = rendered["levels"][0]
        self.assertEqual(first["count"], 20)
        self.assertEqual(len(first["positions"]), 20 * 3)
        self.assertEqual(len(first["biomes"]), 20)
        self.assertEqual(len(first["elevations"]), 20)
        self.assertEqual(rendered["biomes"][0]["name"], "ocean")


class LatLonForPointTests(unittest.TestCase):
    def test_north_pole_returns_ninety_degrees(self) -> None:
        latitude, longitude = lat_lon_for_point((0.0, 0.0, 1.0))

        self.assertAlmostEqual(latitude, 90.0)
        self.assertAlmostEqual(longitude, 0.0)

    def test_equator_zero_meridian(self) -> None:
        latitude, longitude = lat_lon_for_point((1.0, 0.0, 0.0))

        self.assertAlmostEqual(latitude, 0.0)
        self.assertAlmostEqual(longitude, 0.0)


class WebglViewerHtmlTests(unittest.TestCase):
    def test_render_embeds_payload_and_uses_webgl2(self) -> None:
        payload = build_sphere_point_payload(counts=(20, 80))

        html = render_webgl_viewer_html(payload)

        self.assertIn("webgl2", html)
        self.assertNotIn("__SPHERE_PAYLOAD__", html)
        self.assertIn('"kind":"sphere-points-lod"', html)
        for letter in ("W", "A", "S", "D"):
            self.assertIn(f"<kbd>{letter}</kbd>", html)

    def test_render_rejects_non_lod_payload(self) -> None:
        with self.assertRaises(ValueError):
            render_webgl_viewer_html({"kind": "single", "levels": []})

    def test_write_creates_file(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            from pathlib import Path

            output = Path(tmp) / "viewer.html"
            payload = build_sphere_point_payload(counts=(20, 80))
            result = write_webgl_viewer_html(output, payload=payload)

            self.assertEqual(result, output)
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
