"""Resource-only economy strategy simulation prototype."""

from resource_based_economy_strategy.scenarios import (
    create_empty_map_settlement,
    create_player_settlement,
)
from resource_based_economy_strategy.simulation import (
    Building,
    BuildingDefinition,
    DayReport,
    Demographics,
    ENERGY_RESOURCE,
    FastForwardReport,
    Person,
    Recipe,
    Settlement,
    SimulationConfig,
    Technology,
    Weather,
    policy_color,
)

__all__ = [
    "Building",
    "BuildingDefinition",
    "DayReport",
    "Demographics",
    "ENERGY_RESOURCE",
    "FastForwardReport",
    "Person",
    "Recipe",
    "Settlement",
    "SimulationConfig",
    "Technology",
    "Weather",
    "policy_color",
    "create_empty_map_settlement",
    "create_player_settlement",
]
