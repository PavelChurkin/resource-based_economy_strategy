"""Walk a demo planet for a year and report climate / hydropower highlights.

Run with::

    python examples/run_planet_tour.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    from game1 import Climate, build_demo_planet
    from game1.planet import iter_tiles_by_biome

    planet = build_demo_planet()
    climate = Climate()

    print(f"planet: {len(planet)} tiles, surface ≈ {planet.surface_area_km2():.1f} km²")

    rivers = planet.tiles_with_rivers()
    print(f"tiles with rivers: {len(rivers)}")
    for tile in planet.best_hydropower_tiles(limit=3):
        print(
            f"  hydropower {tile.hydropower_potential_kw():.0f} kW @ "
            f"lat={tile.latitude} lon={tile.longitude} "
            f"biome={tile.terrain.biome} drop={tile.terrain.river_drop_m}m"
        )

    print()
    print("biome counts:")
    for biome in (
        "polar",
        "tundra",
        "boreal",
        "temperate",
        "steppe",
        "tropical",
    ):
        tiles = list(iter_tiles_by_biome(planet, biome))
        print(f"  {biome:>10}: {len(tiles)} tiles")

    print()
    print("seasonal sample for first temperate tile every 30 days:")
    sample_tile = next(iter_tiles_by_biome(planet, "temperate"))
    for day in range(0, 360, 30):
        weather = climate.weather_for(
            day=day,
            latitude=sample_tile.latitude,
            solar_baseline=sample_tile.solar_baseline(),
            wind_baseline=sample_tile.wind_baseline(),
            elevation_m=sample_tile.terrain.elevation_m,
        )
        print(
            f"  day {day:>3}: pressure={weather.pressure.value:<11} "
            f"temp={weather.temperature_c:>+6.1f}°C "
            f"solar={weather.solar_factor:.2f} wind={weather.wind_factor:.2f} "
            f"rain={weather.rainfall_mm:>4.1f}mm"
        )


if __name__ == "__main__":
    main()
