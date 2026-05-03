from __future__ import annotations

from game1.planet import build_demo_planet
from resource_based_economy_strategy.simulation import Building, Settlement, Weather


def create_empty_map_settlement(
    people: int,
    initial_resources: dict[str, float] | None = None,
    *,
    latitude: float = 45.0,
    seed: int | None = None,
) -> Settlement:
    """Создать первый лагерь на пустой карте."""

    inventory = dict(initial_resources or {})
    if seed is not None:
        planet = build_demo_planet(seed=seed)
        closest_tile = min(planet, key=lambda tile: abs(tile.latitude - latitude))
        for resource, amount in closest_tile.resources.items():
            inventory[resource] = inventory.get(resource, 0.0) + amount * 0.1
        if closest_tile.terrain.has_river:
            inventory["water"] = inventory.get("water", 0.0) + 30.0
        latitude = closest_tile.latitude

    settlement = Settlement(
        people=people,
        inventory=inventory,
        buildings=[
            Building("camp_center"),
            Building("forager_hut"),
            Building("water_collector"),
        ],
        weather=Weather.for_planet_day(0, latitude=latitude),
        latitude=latitude,
    )
    settlement.unlock_available_technologies()
    return settlement
