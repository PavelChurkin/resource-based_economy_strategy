import unittest

from game1.sphere_points import (
    BIOME_PALETTE,
    FEATURE_LAKE,
    FEATURE_MOUNTAIN,
    FEATURE_RIVER,
    build_sphere_point_level,
    build_sphere_point_payload,
    point_from_lat_lon,
    sample_point_terrain,
)


class CoherentBiomeGenerationTests(unittest.TestCase):
    def test_nearby_points_keep_same_biome_family(self) -> None:
        center = sample_point_terrain(point_from_lat_lon(35.0, 42.0), seed=17)
        neighbors = [
            sample_point_terrain(point_from_lat_lon(35.05, 42.0), seed=17),
            sample_point_terrain(point_from_lat_lon(35.0, 42.05), seed=17),
            sample_point_terrain(point_from_lat_lon(34.95, 41.95), seed=17),
        ]

        self.assertTrue(
            all(sample.biome == center.biome for sample in neighbors),
            [sample.biome for sample in [center, *neighbors]],
        )

    def test_point_level_contains_oceans_land_and_surface_features(self) -> None:
        level = build_sphere_point_level(count=4096, seed=9)
        palette_names = [name for name, _color in BIOME_PALETTE]
        biomes = {palette_names[index] for index in level.biomes}

        self.assertIn("ocean", biomes)
        self.assertTrue(any(name != "ocean" for name in biomes))
        self.assertTrue(any(flags & FEATURE_RIVER for flags in level.features))
        self.assertTrue(any(flags & FEATURE_LAKE for flags in level.features))
        self.assertTrue(any(flags & FEATURE_MOUNTAIN for flags in level.features))

    def test_render_payload_exports_feature_flags(self) -> None:
        payload = build_sphere_point_payload(counts=(32, 64), seed=3)
        rendered = payload.to_render_payload()
        first = rendered["levels"][0]

        self.assertIn("features", first)
        self.assertEqual(len(first["features"]), first["count"])


if __name__ == "__main__":
    unittest.main()
