from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from math import floor, sin, tau
from typing import Mapping, Sequence


Inventory = dict[str, float]
DAYS_PER_WEEK = 7
WEEKS_PER_MONTH = 4
MONTHS_PER_YEAR = 12
DAYS_PER_MONTH = DAYS_PER_WEEK * WEEKS_PER_MONTH
DAYS_PER_YEAR = DAYS_PER_MONTH * MONTHS_PER_YEAR
ADULT_AGE_YEARS = 16
BASE32_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ENERGY_RESOURCE = "energy_mw_day"
BUILDING_FEATURE_MOUNTAIN = 4
POLICY_COLORS = {
    "neutral": "#2f80ed",
    "enemy": "#d63031",
    "ally": "#f2c94c",
    "own": "#2fb344",
}


def to_base32(value: int) -> str:
    if value < 0:
        raise ValueError("value must be non-negative")
    if value == 0:
        return BASE32_ALPHABET[0]
    digits: list[str] = []
    base = len(BASE32_ALPHABET)
    while value:
        value, remainder = divmod(value, base)
        digits.append(BASE32_ALPHABET[remainder])
    return "".join(reversed(digits))


def policy_color(relation: str) -> str:
    try:
        return POLICY_COLORS[relation]
    except KeyError as exc:
        raise ValueError(f"unknown policy relation: {relation}") from exc


@dataclass
class Person:
    id: str
    name: str
    age_days: int
    alive: bool = True
    death_cause: str | None = None

    @classmethod
    def from_index(cls, index: int, *, age_years: int = ADULT_AGE_YEARS) -> Person:
        if index < 1:
            raise ValueError("index must be positive")
        return cls(
            id=to_base32(index).rjust(4, "0"),
            name=f"Чел{index}",
            age_days=age_years * DAYS_PER_YEAR,
        )

    @property
    def age_years(self) -> int:
        return self.age_days // DAYS_PER_YEAR

    @property
    def is_adult(self) -> bool:
        return self.alive and self.age_days >= ADULT_AGE_YEARS * DAYS_PER_YEAR


@dataclass(frozen=True)
class Demographics:
    adults: int
    children: int
    unemployed: int
    vacancies: int


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
    construction_cost: Mapping[str, float] = field(default_factory=dict)
    required_buildings: tuple[str, ...] = ()
    vacancies: int = 0
    storage_capacity_tons: float = 0.0
    warmth_protection: float = 0.0
    affected_by_precipitation: bool = False
    affected_by_solar: bool = False
    affected_by_wind: bool = False
    allowed_biomes: tuple[str, ...] = ()
    required_features: int = 0
    unique: bool = False


@dataclass
class Building:
    name: str
    active: bool = True
    point_id: int | None = None
    owner: str | None = None


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
    status_events: list[str] = field(default_factory=list)
    demographics: Demographics | None = None


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
        default_factory=lambda: {"food": 0.002, "water": 0.003}
    )
    cold_temperature_c: float = 8.0
    energy_mw_day_per_person_when_cold: float = 0.001
    base_carry_capacity_per_person: float = 16.0
    birth_interval_days: int = 8 * DAYS_PER_MONTH
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
    player_nickname: str | None = None
    citizens: list[Person] = field(default_factory=list)
    status_events: list[str] = field(default_factory=list)
    _next_person_index: int = 1

    def __post_init__(self) -> None:
        if self.citizens:
            self._sync_people_from_citizens()
            self._next_person_index = max(
                self._person_index(person) for person in self.citizens
            ) + 1

    def clone(self) -> Settlement:
        return deepcopy(self)

    def living_citizens(self) -> list[Person]:
        return [person for person in self.citizens if person.alive]

    @property
    def daily_labor_capacity(self) -> float:
        if self.citizens:
            return float(sum(1 for person in self.living_citizens() if person.is_adult))
        return float(self.people)

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
        return (
            self.daily_labor_capacity
            * self.config.base_carry_capacity_per_person
            * multiplier
        )

    def demographics(self) -> Demographics:
        if self.citizens:
            living = self.living_citizens()
            adults = sum(1 for person in living if person.is_adult)
            children = len(living) - adults
        else:
            adults = self.people
            children = 0
        vacancies = 0
        for building in self.buildings:
            if building.active:
                vacancies += self._definition_for(building).vacancies
        return Demographics(
            adults=adults,
            children=children,
            unemployed=max(0, adults - vacancies),
            vacancies=vacancies,
        )

    def available_building_names(self) -> list[str]:
        active_buildings = {
            building.name for building in self.buildings if building.active
        }
        available: list[str] = []
        for name, definition in self.config.building_definitions.items():
            if definition.unique and name in active_buildings:
                continue
            if all(
                requirement in active_buildings
                for requirement in definition.required_buildings
            ):
                available.append(name)
        return available

    def plan_building(
        self,
        name: str,
        *,
        point_id: int | None = None,
        point_biome: str | None = None,
        point_features: int = 0,
    ) -> Building:
        if name not in self.config.building_definitions:
            raise KeyError(f"Unknown building definition: {name}")
        if name not in self.available_building_names():
            raise ValueError(f"building {name!r} is not unlocked yet")
        definition = self.config.building_definitions[name]
        if point_id is not None and any(
            building.active and building.point_id == point_id
            for building in self.buildings
        ):
            raise ValueError(f"point #{point_id} already has a building")
        if definition.allowed_biomes and point_biome not in definition.allowed_biomes:
            expected = ", ".join(definition.allowed_biomes)
            raise ValueError(f"building {name!r} can be placed only on: {expected}")
        if (
            definition.required_features
            and (point_features & definition.required_features)
            != definition.required_features
        ):
            raise ValueError(f"building {name!r} cannot be placed on this point")
        if not _has_resources(self.inventory, definition.construction_cost):
            raise ValueError(f"not enough resources to build {name!r}")
        for resource, amount in definition.construction_cost.items():
            _take_resource(self.inventory, resource, amount)
        building = Building(
            name=name,
            point_id=point_id,
            owner=self.player_nickname,
        )
        self.buildings.append(building)
        location = f" в точке #{point_id}" if point_id is not None else ""
        self.status_events.append(f"Запланирована постройка {name}{location}.")
        return building

    def tick(self, weather: Weather | None = None) -> DayReport:
        self._sync_people_from_citizens()
        event_start = len(self.status_events)
        if weather is not None:
            self.weather = weather
        elif self.latitude is not None:
            self.weather = Weather.for_planet_day(self.day, self.latitude)
        consumed: Inventory = {}
        produced: Inventory = {}
        transformed: Inventory = {}
        unlocked = self.unlock_available_technologies()

        remaining_logistics = self.daily_logistics_capacity
        remaining_labor = self.daily_labor_capacity

        for building in self.buildings:
            if not building.active:
                continue
            definition = self._definition_for(building)
            remaining_labor, remaining_logistics = self._apply_building_io(
                definition,
                produced,
                consumed,
                remaining_labor,
                remaining_logistics,
            )
            remaining_labor, remaining_logistics = self._apply_recipes(
                definition,
                transformed,
                consumed,
                remaining_labor,
                remaining_logistics,
            )

        (
            need_consumed,
            missing_needs,
            needs_satisfied_ratio,
            resource_deaths,
        ) = self._consume_needs()
        _merge_inventory(consumed, need_consumed)
        deaths, births = self._advance_population(
            needs_satisfied_ratio,
            missing_needs,
            resource_deaths,
        )

        self.day += 1
        unlocked.extend(self.unlock_available_technologies())
        events = list(self.status_events[event_start:])
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
            status_events=events,
            demographics=self.demographics(),
        )

    def tick_week(self) -> FastForwardReport:
        start_day = self.day
        reports = [self.tick() for _ in range(7)]
        demographics = self.demographics()
        self.status_events.append(
            "Неделя "
            f"{self.day // 7}: взрослые {demographics.adults}, "
            f"дети {demographics.children}, безработные {demographics.unemployed}, "
            f"вакансии {demographics.vacancies}."
        )
        average = sum(report.needs_satisfied_ratio for report in reports) / 7
        return FastForwardReport(
            days=7,
            start_day=start_day,
            end_day=self.day,
            average_needs_satisfied_ratio=average,
            reports=reports,
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
        remaining_labor: float,
        remaining_logistics: float,
    ) -> tuple[float, float]:
        if not definition.daily_inputs and not definition.daily_outputs:
            return remaining_labor, remaining_logistics
        if not _has_resources(self.inventory, definition.daily_inputs):
            return remaining_labor, remaining_logistics
        required_labor = float(definition.vacancies)
        if required_labor > remaining_labor:
            return remaining_labor, remaining_logistics
        transport_mass = sum(definition.daily_inputs.values()) + sum(
            definition.daily_outputs.values()
        )
        if transport_mass > remaining_logistics:
            return remaining_labor, remaining_logistics
        factor = self._weather_factor(definition)
        for resource, amount in definition.daily_inputs.items():
            _take_resource(self.inventory, resource, amount)
            _add_resource(consumed, resource, amount)
        for resource, amount in definition.daily_outputs.items():
            actual_amount = amount * factor
            _add_resource(self.inventory, resource, actual_amount)
            _add_resource(produced, resource, actual_amount)
        return remaining_labor - required_labor, remaining_logistics - transport_mass

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

    def _consume_needs(
        self,
    ) -> tuple[Inventory, Inventory, float, list[tuple[Person, str]]]:
        if self.citizens:
            return self._consume_citizen_needs()

        needs = {
            resource: amount * self.people
            for resource, amount in self.config.per_person_daily_needs.items()
        }
        if self.weather.temperature_c < self.config.cold_temperature_c:
            needs[ENERGY_RESOURCE] = (
                self.config.energy_mw_day_per_person_when_cold * self.people
            )
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
            return consumed, missing, 1.0, []
        return consumed, missing, total_satisfied / total_need, []

    def _consume_citizen_needs(
        self,
    ) -> tuple[Inventory, Inventory, float, list[tuple[Person, str]]]:
        per_person_needs = dict(self.config.per_person_daily_needs)
        if self.weather.temperature_c < self.config.cold_temperature_c:
            per_person_needs[ENERGY_RESOURCE] = (
                self.config.energy_mw_day_per_person_when_cold
            )

        living = self.living_citizens()
        housing_shortfall = max(0, len(living) - self.housing_capacity)
        total_need = sum(per_person_needs.values()) * len(living) + housing_shortfall
        total_satisfied = 0.0
        consumed: Inventory = {}
        missing: Inventory = {}
        resource_deaths: list[tuple[Person, str]] = []

        if housing_shortfall:
            missing["housing"] = float(housing_shortfall)

        for person in living:
            death_cause: str | None = None
            for resource, required in per_person_needs.items():
                available = self.inventory.get(resource, 0.0)
                taken = min(available, required)
                if taken > 0:
                    _take_resource(self.inventory, resource, taken)
                    _add_resource(consumed, resource, taken)
                total_satisfied += taken
                if taken + 1e-12 < required:
                    _add_resource(missing, resource, required - taken)
                    if death_cause is None:
                        death_cause = self._death_cause_for_resource(resource)
            if death_cause is not None:
                resource_deaths.append((person, death_cause))

        if total_need == 0:
            return consumed, missing, 1.0, resource_deaths
        return consumed, missing, total_satisfied / total_need, resource_deaths

    def _advance_population(
        self,
        needs_satisfied_ratio: float,
        missing_needs: Mapping[str, float] | None = None,
        resource_deaths: Sequence[tuple[Person, str]] = (),
    ) -> tuple[int, int]:
        if self.citizens:
            return self._advance_citizens(
                needs_satisfied_ratio,
                missing_needs or {},
                resource_deaths,
            )

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
            self.status_events.append(f"Погибло жителей: {deaths}.")

        if needs_satisfied_ratio >= 0.98 and self.people < self.housing_capacity:
            birth_pairs = self.people // 2
            if birth_pairs:
                self.birth_progress += birth_pairs / self.config.birth_interval_days
            births = floor(self.birth_progress + 1e-9)
            if births:
                room = self.housing_capacity - self.people
                births = min(births, room)
                self.people += births
                self.birth_progress -= births
                self.status_events.append(f"Родилось жителей: {births}.")
        return deaths, births

    def _advance_citizens(
        self,
        needs_satisfied_ratio: float,
        missing_needs: Mapping[str, float],
        resource_deaths: Sequence[tuple[Person, str]] = (),
    ) -> tuple[int, int]:
        deaths = 0
        births = 0
        living = self.living_citizens()
        if not living:
            self.people = 0
            return deaths, births

        for person in living:
            was_child = not person.is_adult
            person.age_days += 1
            if was_child and person.is_adult:
                self.status_events.append(
                    f"{person.name} #{person.id} стал взрослым."
                )

        if needs_satisfied_ratio < 0.75:
            self.health -= (0.75 - needs_satisfied_ratio) * (
                self.config.unmet_need_health_penalty
            )
        else:
            self.health = min(1.0, self.health + 0.02)

        for person, cause in resource_deaths:
            if person.alive:
                person.alive = False
                person.death_cause = cause
                deaths += 1
                self.status_events.append(
                    f"{person.name} #{person.id} умер от {cause}."
                )

        cause = self._death_cause_from_missing_needs(missing_needs)
        if self.health <= 0 and deaths == 0:
            deaths = max(1, floor(len(living) * 0.02))
            victims = sorted(living, key=lambda person: person.age_days, reverse=True)[
                :deaths
            ]
            for person in victims:
                person.alive = False
                person.death_cause = cause
                self.status_events.append(
                    f"{person.name} #{person.id} умер от {cause}."
                )
            self.health = 0.25

        old_age_victims = [
            person
            for person in self.living_citizens()
            if person.age_days > 90 * DAYS_PER_YEAR
        ]
        for person in old_age_victims:
            person.alive = False
            person.death_cause = "старости"
            deaths += 1
            self.status_events.append(
                f"{person.name} #{person.id} умер от старости."
            )

        self._sync_people_from_citizens()
        if needs_satisfied_ratio >= 0.98 and self.people < self.housing_capacity:
            adults = sum(1 for person in self.living_citizens() if person.is_adult)
            birth_pairs = adults // 2
            if birth_pairs:
                self.birth_progress += birth_pairs / self.config.birth_interval_days
            births = floor(self.birth_progress + 1e-9)
            if births:
                room = self.housing_capacity - self.people
                births = min(births, room)
                for _ in range(births):
                    person = Person.from_index(self._next_person_index, age_years=0)
                    self._next_person_index += 1
                    self.citizens.append(person)
                    self.status_events.append(
                        f"Родился {person.name} #{person.id}."
                    )
                self.birth_progress -= births
                self._sync_people_from_citizens()
        return deaths, births

    def _death_cause_from_missing_needs(
        self,
        missing_needs: Mapping[str, float],
    ) -> str:
        if missing_needs.get("water", 0.0) > 0:
            return "жажды"
        if missing_needs.get("food", 0.0) > 0:
            return "голода"
        if (
            missing_needs.get(ENERGY_RESOURCE, 0.0) > 0
            or missing_needs.get("housing", 0.0) > 0
        ):
            return "холода"
        return "старости"

    def _death_cause_for_resource(self, resource: str) -> str:
        if resource == "water":
            return "жажды"
        if resource == "food":
            return "голода"
        if resource == ENERGY_RESOURCE:
            return "холода"
        return self._death_cause_from_missing_needs({resource: 1.0})

    def _sync_people_from_citizens(self) -> None:
        if self.citizens:
            self.people = len(self.living_citizens())

    def _person_index(self, person: Person) -> int:
        value = 0
        for char in person.id:
            value = value * len(BASE32_ALPHABET) + BASE32_ALPHABET.index(char)
        return value

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
    "city_center": BuildingDefinition(
        name="city_center",
        housing_capacity=10,
        storage_capacity_tons=120.0,
        unique=True,
    ),
    "camp_center": BuildingDefinition(
        name="camp_center",
        housing_capacity=4,
        vacancies=1,
    ),
    "forager_hut": BuildingDefinition(
        name="forager_hut",
        daily_outputs={"food": 0.008},
        vacancies=2,
    ),
    "water_collector": BuildingDefinition(
        name="water_collector",
        daily_outputs={"water": 0.012},
        affected_by_precipitation=True,
        vacancies=1,
    ),
    "shelter": BuildingDefinition(
        name="shelter",
        housing_capacity=6,
    ),
    "warehouse": BuildingDefinition(
        name="warehouse",
        storage_capacity_tons=250.0,
        construction_cost={"stone": 3.0, "roundwood": 2.0},
        required_buildings=("city_center",),
    ),
    "pump": BuildingDefinition(
        name="pump",
        daily_outputs={"water": 0.08},
        construction_cost={"roundwood": 2.0},
        required_buildings=("city_center",),
        affected_by_precipitation=True,
        vacancies=1,
    ),
    "farm": BuildingDefinition(
        name="farm",
        daily_outputs={"food": 0.06},
        construction_cost={"clay": 2.0, "roundwood": 1.0},
        required_buildings=("city_center",),
        vacancies=2,
    ),
    "quarry": BuildingDefinition(
        name="quarry",
        daily_outputs={"stone": 2.0, "sand": 1.0, "clay": 1.0},
        construction_cost={"stone": 4.0},
        required_buildings=("city_center",),
        vacancies=3,
    ),
    "stone_quarry": BuildingDefinition(
        name="stone_quarry",
        daily_outputs={"stone": 4.0},
        construction_cost={"stone": 8.0, "roundwood": 2.0},
        required_buildings=("city_center",),
        vacancies=4,
    ),
    "lumberjack_site": BuildingDefinition(
        name="lumberjack_site",
        daily_outputs={"roundwood": 4.0},
        construction_cost={"stone": 2.0, "tools": 0.2},
        required_buildings=("stone_quarry",),
        vacancies=4,
    ),
    "mine": BuildingDefinition(
        name="mine",
        daily_outputs={"raw_metal": 0.8},
        construction_cost={"tools": 1.0, "roundwood": 6.0},
        required_buildings=("city_center",),
        vacancies=4,
        allowed_biomes=("mountain",),
        required_features=BUILDING_FEATURE_MOUNTAIN,
    ),
    "housing1": BuildingDefinition(
        name="housing1",
        housing_capacity=5,
        construction_cost={"clay": 5.0},
        required_buildings=("warehouse",),
        warmth_protection=0.2,
    ),
    "housing2": BuildingDefinition(
        name="housing2",
        housing_capacity=25,
        construction_cost={"roundwood": 12.0},
        required_buildings=("lumberjack_site",),
        warmth_protection=0.45,
    ),
    "housing3": BuildingDefinition(
        name="housing3",
        housing_capacity=100,
        construction_cost={"plank": 28.0},
        required_buildings=("sawmill",),
        warmth_protection=0.62,
    ),
    "housing4": BuildingDefinition(
        name="housing4",
        housing_capacity=500,
        construction_cost={"brick": 120.0},
        required_buildings=("brick_factory",),
        warmth_protection=0.78,
    ),
    "housing5": BuildingDefinition(
        name="housing5",
        housing_capacity=5000,
        construction_cost={"concrete": 1100.0, "metal": 120.0},
        required_buildings=("foundry",),
        warmth_protection=0.92,
    ),
    "brick_factory": BuildingDefinition(
        name="brick_factory",
        recipes=[Recipe(inputs={"clay": 2.0}, outputs={"brick": 1.6})],
        construction_cost={"stone": 12.0, "roundwood": 4.0},
        required_buildings=("quarry",),
        vacancies=6,
    ),
    "forge": BuildingDefinition(
        name="forge",
        recipes=[
            Recipe(
                inputs={"raw_metal": 1.5, "roundwood": 0.5},
                outputs={"tools": 1.0},
            )
        ],
        construction_cost={"stone": 18.0, "roundwood": 6.0},
        required_buildings=("stone_quarry",),
        vacancies=4,
    ),
    "sawmill": BuildingDefinition(
        name="sawmill",
        recipes=[
            Recipe(inputs={"roundwood": 2.0}, outputs={"plank": 3.0, "sawdust": 1.0}),
        ],
        construction_cost={"stone": 8.0, "roundwood": 8.0},
        required_buildings=("lumberjack_site",),
        vacancies=4,
    ),
    "foundry": BuildingDefinition(
        name="foundry",
        recipes=[
            Recipe(
                inputs={"raw_metal": 3.0, "roundwood": 1.0},
                outputs={"metal": 1.8},
            )
        ],
        construction_cost={"stone": 20.0, "brick": 10.0},
        required_buildings=("forge",),
        vacancies=8,
    ),
    "workshop": BuildingDefinition(
        name="workshop",
        recipes=[
            Recipe(
                inputs={"roundwood": 2.0, "stone": 1.0},
                outputs={"plank": 2.0},
            )
        ],
    ),
    "boiler_house": BuildingDefinition(
        name="boiler_house",
        recipes=[
            Recipe(inputs={"roundwood": 1.0}, outputs={ENERGY_RESOURCE: 0.04}),
            Recipe(inputs={"coal": 0.5}, outputs={ENERGY_RESOURCE: 0.08}),
        ],
        construction_cost={"stone": 6.0, "roundwood": 4.0},
        required_buildings=("city_center",),
        vacancies=2,
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
        daily_inputs={"water": 0.03, "electricity": 1.0},
        daily_outputs={"food": 0.08},
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
    "roundwood_processing": Technology(
        id="roundwood_processing",
        name="Roundwood processing",
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
