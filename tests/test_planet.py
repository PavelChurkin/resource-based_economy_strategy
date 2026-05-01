import unittest

from game1.planet import (
    Planet,
    PlanetTile,
    Terrain,
    build_demo_planet,
    iter_tiles_by_biome,
)


class PlanetTileTests(unittest.TestCase):
    def test_hydropower_zero_without_river(self) -> None:
        tile = PlanetTile(
            latitude=10,
            longitude=20,
            terrain=Terrain(
                elevation_m=300,
                river_drop_m=0,
                biome="temperate",
                has_river=False,
            ),
        )
        self.assertEqual(tile.hydropower_potential_kw(), 0.0)

    def test_hydropower_scales_with_drop(self) -> None:
        small = PlanetTile(
            latitude=0,
            longitude=0,
            terrain=Terrain(
                elevation_m=400,
                river_drop_m=10,
                biome="temperate",
                has_river=True,
            ),
        )
        big = PlanetTile(
            latitude=0,
            longitude=10,
            terrain=Terrain(
                elevation_m=400,
                river_drop_m=40,
                biome="temperate",
                has_river=True,
            ),
        )
        self.assertGreater(big.hydropower_potential_kw(), small.hydropower_potential_kw())

    def test_solar_baseline_decreases_with_latitude(self) -> None:
        equator = PlanetTile(
            latitude=0,
            longitude=0,
            terrain=Terrain(0, 0, "tropical", False),
        )
        polar = PlanetTile(
            latitude=85,
            longitude=0,
            terrain=Terrain(0, 0, "polar", False),
        )
        self.assertGreater(equator.solar_baseline(), polar.solar_baseline())

    def test_invalid_biome_raises(self) -> None:
        with self.assertRaises(ValueError):
            Terrain(elevation_m=0, river_drop_m=0, biome="banana", has_river=False)

    def test_river_drop_requires_river(self) -> None:
        with self.assertRaises(ValueError):
            Terrain(elevation_m=0, river_drop_m=5, biome="temperate", has_river=False)

    def test_latitude_bounds(self) -> None:
        with self.assertRaises(ValueError):
            PlanetTile(
                latitude=120,
                longitude=0,
                terrain=Terrain(0, 0, "polar", False),
            )


class DemoPlanetTests(unittest.TestCase):
    def test_demo_planet_is_deterministic(self) -> None:
        a = build_demo_planet()
        b = build_demo_planet()
        self.assertEqual(len(a), len(b))
        for tile_a, tile_b in zip(a, b):
            self.assertEqual(tile_a.latitude, tile_b.latitude)
            self.assertEqual(tile_a.longitude, tile_b.longitude)
            self.assertEqual(tile_a.terrain, tile_b.terrain)

    def test_demo_planet_has_rivers_and_polar_caps(self) -> None:
        planet = build_demo_planet()
        self.assertTrue(any(tile.terrain.has_river for tile in planet))
        polar_tiles = list(iter_tiles_by_biome(planet, "polar"))
        self.assertTrue(polar_tiles)
        for tile in polar_tiles:
            self.assertFalse(tile.terrain.has_river)

    def test_best_hydropower_tiles_sorted(self) -> None:
        planet = build_demo_planet()
        ranked = planet.best_hydropower_tiles(limit=3)
        if len(ranked) > 1:
            values = [t.hydropower_potential_kw() for t in ranked]
            self.assertEqual(values, sorted(values, reverse=True))

    def test_surface_area_scales_with_radius(self) -> None:
        small = Planet(tiles=[], radius_km=1.0)
        big = Planet(tiles=[], radius_km=10.0)
        self.assertAlmostEqual(big.surface_area_km2() / small.surface_area_km2(), 100.0)


if __name__ == "__main__":
    unittest.main()
