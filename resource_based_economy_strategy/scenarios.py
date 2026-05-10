from __future__ import annotations

from game1.planet import build_demo_planet
from resource_based_economy_strategy.simulation import (
    DAYS_PER_YEAR,
    Building,
    Person,
    Settlement,
    Weather,
)


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


def create_player_settlement(
    nickname: str,
    *,
    latitude: float = 45.0,
    seed: int | None = None,
    city_center_point_id: int | None = 0,
) -> Settlement:
    """Create the player settlement with optional placed city center."""

    people = 10
    daily_food = 0.002
    daily_water = 0.003
    inventory = {
        "food": people * daily_food * DAYS_PER_YEAR,
        "water": people * daily_water * DAYS_PER_YEAR,
        "roundwood": 80.0,
        "stone": 80.0,
        "sand": 30.0,
        "clay": 40.0,
        "raw_metal": 12.0,
        "tools": 2.0,
        "coal": 8.0,
    }
    if seed is not None:
        planet = build_demo_planet(seed=seed)
        closest_tile = min(planet, key=lambda tile: abs(tile.latitude - latitude))
        for resource, amount in closest_tile.resources.items():
            inventory[resource] = inventory.get(resource, 0.0) + amount * 0.1
        if closest_tile.terrain.has_river or closest_tile.terrain.has_lake:
            inventory["water"] += 60.0
        latitude = closest_tile.latitude

    buildings = []
    if city_center_point_id is not None:
        buildings.append(
            Building("city_center", point_id=city_center_point_id, owner=nickname)
        )

    settlement = Settlement(
        people=people,
        inventory=inventory,
        buildings=buildings,
        weather=Weather.for_planet_day(0, latitude=latitude),
        latitude=latitude,
        player_nickname=nickname,
        citizens=[Person.from_index(index) for index in range(1, people + 1)],
    )
    if city_center_point_id is None:
        settlement.status_events.append(
            f"Игрок {nickname} вошёл в игру: выберите точку для центра города."
        )
    else:
        settlement.status_events.append(
            f"Игрок {nickname} вошёл в игру: создано 10 жителей."
        )
    settlement.unlock_available_technologies()
    return settlement
