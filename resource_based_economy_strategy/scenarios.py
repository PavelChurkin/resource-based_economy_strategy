from __future__ import annotations

from resource_based_economy_strategy.simulation import Building, Settlement, Weather


def create_empty_map_settlement(
    people: int,
    initial_resources: dict[str, float] | None = None,
    *,
    latitude: float = 45.0,
    seed: int | None = None,
) -> Settlement:
    """Create the first camp on an empty map.

    The seed is accepted now to keep scenario construction stable when stochastic
    events are added later. The current prototype is deterministic.
    """

    del seed
    inventory = dict(initial_resources or {})
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
