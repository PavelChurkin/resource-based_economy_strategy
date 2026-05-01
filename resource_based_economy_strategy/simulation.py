from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from math import floor, sin, tau
from typing import Mapping, Sequence


Inventory = dict[str, float]


@dataclass(frozen=True)
class Recipe:
    """Transforms resources using labor and logistics, never currency."""

    inputs: Mapping[str, float]
    outputs: Mapping[str, float]
    labor_days: float = 1.0

    @property
    def transport_mass(self) -> float:
        return sum(self.inputs.values()) + sum(self.outputs.values())


@dataclass(frozen=True)
class BuildingDefinition:
    name: str
    daily_inputs: Mapping[str, float] = field(default_factory=dict)
    daily_outputs: Mapping[str, float] = field(default_factory=dict)
    recipes: Sequence[Recipe] = field(default_factory=tuple)
    housing_capacity: int = 0
    affected_by_precipitation: bool = False
    affected_by_solar: bool = False
    affected_by_wind: bool = False


@dataclass
class Building:
    name: str
    active: bool = True


@dataclass(frozen=True)
class Technology:
    id: str
    name: str
    description: str
    required_resources: Mapping[str, float] = field(default_factory=dict)
    required_buildings: tuple[str, ...] = ()
    required_technologies: tuple[str, ...] = ()
    logistics_multiplier: float = 1.0

    def can_unlock(self, settlement: Settlement) -> bool:
        if self.id in settlement.unlocked_technologies:
            return False
        if any(
            requirement not in settlement.unlocked_technologies
            for requirement in self.required_technologies
        ):
            return False
        active_building_names = {
            building.name for building in settlement.buildings if building.active
        }
        if any(name not in active_building_names for name in self.required_buildings):
            return False
        return all(
            settlement.inventory.get(resource, 0) >= amount
            for resource, amount in self.required_resources.items()
        )


@dataclass(frozen=True)
class Weather:
    temperature_c: float
    precipitation_mm: float
    solar_factor: float
    wind_factor: float
    pressure_system: str

    @classmethod
    def stable(cls) -> Weather:
        return cls(
            temperature_c=18.0,
            precipitation_mm=7.5,
            solar_factor=1.0,
            wind_factor=1.0,
            pressure_system="stable",
        )

    @classmethod
    def for_planet_day(cls, day: int, latitude: float = 45.0) -> Weather:
        """Deterministic climate approximation for a spherical planet tile."""

        season = sin((day % 365) / 365 * tau)
        latitude_penalty = abs(latitude) / 90
        temperature_c = 21 + 12 * season - 22 * latitude_penalty
        cyclone = (day // 9 + int(abs(latitude))) % 4 in (0, 1)
        if cyclone:
            precipitation_mm = 8 + 4 * max(season, 0)
            solar_factor = 0.55
            wind_factor = 1.35
            pressure_system = "cyclone"
        else:
            precipitation_mm = 0.8
            solar_factor = 1.15
            wind_factor = 0.75
            pressure_system = "anticyclone"
        return cls(
            temperature_c=temperature_c,
            precipitation_mm=precipitation_mm,
            solar_factor=solar_factor,
            wind_factor=wind_factor,
            pressure_system=pressure_system,
        )


@dataclass
class DayReport:
    day: int
    population: int
    consumed: Inventory
    produced: Inventory
    transformed: Inventory
    missing_needs: Inventory
    needs_satisfied_ratio: float
    unlocked_technologies: list[str]
    deaths: int = 0
    births: int = 0


@dataclass
class FastForwardReport:
    days: int
    start_day: int
    end_day: int
    average_needs_satisfied_ratio: float
    reports: list[DayReport]


@dataclass
class SimulationConfig:
    building_definitions: Mapping[str, BuildingDefinition] = field(
        default_factory=lambda: dict(DEFAULT_BUILDINGS)
    )
    technologies: Mapping[str, Technology] = field(
        default_factory=lambda: dict(DEFAULT_TECHNOLOGIES)
    )
    per_person_daily_needs: Mapping[str, float] = field(
        default_factory=lambda: {"food": 1.8, "water": 3.0}
    )
    cold_temperature_c: float = 8.0
    heat_per_person_when_cold: float = 1.2
    base_carry_capacity_per_person: float = 16.0
    healthy_birth_rate_per_person_day: float = 0.0007
    unmet_need_health_penalty: float = 0.09


@dataclass
class Settlement:
    people: int
    inventory: Inventory
    buildings: list[Building] = field(default_factory=list)
    config: SimulationConfig = field(default_factory=SimulationConfig)
    weather: Weather = field(default_factory=Weather.stable)
    latitude: float | None = None
    day: int = 0
    unlocked_technologies: set[str] = field(default_factory=set)
    health: float = 1.0
    birth_progress: float = 0.0

    def clone(self) -> Settlement:
        return deepcopy(self)

    @property
    def housing_capacity(self) -> int:
        capacity = 0
        for building in self.buildings:
            definition = self._definition_for(building)
            if building.active:
                capacity += definition.housing_capacity
        return capacity

    @property
    def daily_logistics_capacity(self) -> float:
        multiplier = 1.0
        for technology_id in self.unlocked_technologies:
            technology = self.config.technologies.get(technology_id)
            if technology is not None:
                multiplier *= technology.logistics_multiplier
        return self.people * self.config.base_carry_capacity_per_person * multiplier

    def tick(self, weather: Weather | None = None) -> DayReport:
        if weather is not None:
            self.weather = weather
        elif self.latitude is not None:
            self.weather = Weather.for_planet_day(self.day, self.latitude)
        consumed: Inventory = {}
        produced: Inventory = {}
        transformed: Inventory = {}
        unlocked = self.unlock_available_technologies()

        remaining_logistics = self.daily_logistics_capacity
        remaining_labor = float(self.people)

        for building in self.buildings:
            if not building.active:
                continue
            definition = self._definition_for(building)
            remaining_logistics = self._apply_building_io(
                definition,
                produced,
                consumed,
                remaining_logistics,
            )
            remaining_labor, remaining_logistics = self._apply_recipes(
                definition,
                transformed,
                consumed,
                remaining_labor,
                remaining_logistics,
            )

        need_consumed, missing_needs, needs_satisfied_ratio = self._consume_needs()
        _merge_inventory(consumed, need_consumed)
        deaths, births = self._advance_population(needs_satisfied_ratio)

        self.day += 1
        unlocked.extend(self.unlock_available_technologies())
        return DayReport(
            day=self.day,
            population=self.people,
            consumed=consumed,
            produced=produced,
            transformed=transformed,
            missing_needs=missing_needs,
            needs_satisfied_ratio=needs_satisfied_ratio,
            unlocked_technologies=sorted(set(unlocked)),
            deaths=deaths,
            births=births,
        )

    def fast_forward(self, days: int) -> FastForwardReport:
        if days < 0:
            raise ValueError("days must be non-negative")
        start_day = self.day
        reports = [self.tick() for _ in range(days)]
        if reports:
            average = sum(report.needs_satisfied_ratio for report in reports) / days
        else:
            average = 1.0
        return FastForwardReport(
            days=days,
            start_day=start_day,
            end_day=self.day,
            average_needs_satisfied_ratio=average,
            reports=reports,
        )

    def unlock_available_technologies(self) -> list[str]:
        unlocked: list[str] = []
        changed = True
        while changed:
            changed = False
            for technology in self.config.technologies.values():
                if technology.can_unlock(self):
                    self.unlocked_technologies.add(technology.id)
                    unlocked.append(technology.id)
                    changed = True
        return unlocked

    def _apply_building_io(
        self,
        definition: BuildingDefinition,
        produced: Inventory,
        consumed: Inventory,
        remaining_logistics: float,
    ) -> float:
        if not _has_resources(self.inventory, definition.daily_inputs):
            return remaining_logistics
        transport_mass = sum(definition.daily_inputs.values()) + sum(
            definition.daily_outputs.values()
        )
        if transport_mass > remaining_logistics:
            return remaining_logistics
        factor = self._weather_factor(definition)
        for resource, amount in definition.daily_inputs.items():
            _take_resource(self.inventory, resource, amount)
            _add_resource(consumed, resource, amount)
        for resource, amount in definition.daily_outputs.items():
            actual_amount = amount * factor
            _add_resource(self.inventory, resource, actual_amount)
            _add_resource(produced, resource, actual_amount)
        return remaining_logistics - transport_mass

    def _apply_recipes(
        self,
        definition: BuildingDefinition,
        transformed: Inventory,
        consumed: Inventory,
        remaining_labor: float,
        remaining_logistics: float,
    ) -> tuple[float, float]:
        for recipe in definition.recipes:
            if remaining_labor < recipe.labor_days:
                continue
            if remaining_logistics < recipe.transport_mass:
                continue
            if not _has_resources(self.inventory, recipe.inputs):
                continue
            for resource, amount in recipe.inputs.items():
                _take_resource(self.inventory, resource, amount)
                _add_resource(consumed, resource, amount)
            for resource, amount in recipe.outputs.items():
                _add_resource(self.inventory, resource, amount)
                _add_resource(transformed, resource, amount)
            remaining_labor -= recipe.labor_days
            remaining_logistics -= recipe.transport_mass
        return remaining_labor, remaining_logistics

    def _consume_needs(self) -> tuple[Inventory, Inventory, float]:
        needs = {
            resource: amount * self.people
            for resource, amount in self.config.per_person_daily_needs.items()
        }
        if self.weather.temperature_c < self.config.cold_temperature_c:
            needs["heat"] = self.config.heat_per_person_when_cold * self.people
        if self.people > self.housing_capacity:
            unhoused = self.people - self.housing_capacity
            needs["housing"] = float(unhoused)

        consumed: Inventory = {}
        missing: Inventory = {}
        total_need = sum(needs.values())
        total_satisfied = 0.0
        for resource, required in needs.items():
            available = self.inventory.get(resource, 0.0)
            taken = min(available, required)
            if taken > 0:
                _take_resource(self.inventory, resource, taken)
                _add_resource(consumed, resource, taken)
            total_satisfied += taken
            if taken < required:
                missing[resource] = required - taken
        if total_need == 0:
            return consumed, missing, 1.0
        return consumed, missing, total_satisfied / total_need

    def _advance_population(self, needs_satisfied_ratio: float) -> tuple[int, int]:
        deaths = 0
        births = 0
        if self.people <= 0:
            return deaths, births

        if needs_satisfied_ratio < 0.75:
            self.health -= (0.75 - needs_satisfied_ratio) * (
                self.config.unmet_need_health_penalty
            )
        else:
            self.health = min(1.0, self.health + 0.02)

        if self.health <= 0:
            deaths = max(1, floor(self.people * 0.02))
            self.people = max(0, self.people - deaths)
            self.health = 0.25

        if needs_satisfied_ratio >= 0.98 and self.people < self.housing_capacity:
            self.birth_progress += self.people * (
                self.config.healthy_birth_rate_per_person_day
            )
            births = floor(self.birth_progress)
            if births:
                room = self.housing_capacity - self.people
                births = min(births, room)
                self.people += births
                self.birth_progress -= births
        return deaths, births

    def _weather_factor(self, definition: BuildingDefinition) -> float:
        factor = 1.0
        if definition.affected_by_precipitation:
            factor *= 0.25 + self.weather.precipitation_mm / 10
        if definition.affected_by_solar:
            factor *= self.weather.solar_factor
        if definition.affected_by_wind:
            factor *= self.weather.wind_factor
        return max(factor, 0.0)

    def _definition_for(self, building: Building) -> BuildingDefinition:
        try:
            return self.config.building_definitions[building.name]
        except KeyError as exc:
            raise KeyError(f"Unknown building definition: {building.name}") from exc


def _has_resources(inventory: Mapping[str, float], costs: Mapping[str, float]) -> bool:
    return all(
        inventory.get(resource, 0.0) >= amount for resource, amount in costs.items()
    )


def _take_resource(inventory: Inventory, resource: str, amount: float) -> None:
    remaining = inventory.get(resource, 0.0) - amount
    if remaining <= 1e-9:
        inventory.pop(resource, None)
    else:
        inventory[resource] = remaining


def _add_resource(inventory: Inventory, resource: str, amount: float) -> None:
    if amount <= 0:
        return
    inventory[resource] = inventory.get(resource, 0.0) + amount


def _merge_inventory(target: Inventory, source: Mapping[str, float]) -> None:
    for resource, amount in source.items():
        _add_resource(target, resource, amount)


DEFAULT_BUILDINGS: dict[str, BuildingDefinition] = {
    "camp_center": BuildingDefinition(
        name="camp_center",
        housing_capacity=4,
    ),
    "forager_hut": BuildingDefinition(
        name="forager_hut",
        daily_outputs={"food": 4.0},
    ),
    "water_collector": BuildingDefinition(
        name="water_collector",
        daily_outputs={"water": 7.0},
        affected_by_precipitation=True,
    ),
    "shelter": BuildingDefinition(
        name="shelter",
        housing_capacity=6,
    ),
    "sawmill": BuildingDefinition(
        name="sawmill",
        recipes=[
            Recipe(inputs={"wood": 2.0}, outputs={"plank": 3.0, "sawdust": 1.0})
        ],
    ),
    "workshop": BuildingDefinition(
        name="workshop",
        recipes=[
            Recipe(
                inputs={"wood": 2.0, "stone": 1.0},
                outputs={"roundwood": 1.0, "plank": 1.0},
            )
        ],
    ),
    "wind_turbine": BuildingDefinition(
        name="wind_turbine",
        daily_outputs={"electricity": 8.0},
        affected_by_wind=True,
    ),
    "solar_panel": BuildingDefinition(
        name="solar_panel",
        daily_outputs={"electricity": 12.0},
        affected_by_solar=True,
    ),
    "greenhouse": BuildingDefinition(
        name="greenhouse",
        daily_inputs={"water": 3.0, "electricity": 1.0},
        daily_outputs={"food": 8.0},
    ),
    "infirmary": BuildingDefinition(
        name="infirmary",
        daily_inputs={"herbs": 1.0},
        daily_outputs={"medicine": 1.0},
    ),
}


DEFAULT_TECHNOLOGIES: dict[str, Technology] = {
    "basic_settlement": Technology(
        id="basic_settlement",
        name="Basic settlement",
        description="A staffed camp can distribute stored resources without currency.",
        required_buildings=("camp_center",),
    ),
    "wood_processing": Technology(
        id="wood_processing",
        name="Wood processing",
        description="Boards and sawdust unlock more durable construction chains.",
        required_resources={"plank": 3.0},
    ),
    "wheel": Technology(
        id="wheel",
        name="Wheel",
        description="Round timber and planks make carts possible.",
        required_resources={"plank": 4.0, "roundwood": 2.0},
        logistics_multiplier=2.25,
    ),
    "renewable_electricity": Technology(
        id="renewable_electricity",
        name="Renewable electricity",
        description="Wind or solar generation starts the electrical production chain.",
        required_buildings=("wind_turbine",),
    ),
    "medicine": Technology(
        id="medicine",
        name="Medicine",
        description="Herbal processing enables treatment of injuries and infections.",
        required_buildings=("infirmary",),
        required_resources={"medicine": 1.0},
    ),
}
