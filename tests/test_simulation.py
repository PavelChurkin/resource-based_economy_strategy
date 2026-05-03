import unittest
from io import StringIO

from resource_based_economy_strategy.cli import run_managed_simulation
from resource_based_economy_strategy.scenarios import create_empty_map_settlement
from resource_based_economy_strategy.simulation import (
    Building,
    BuildingDefinition,
    Recipe,
    SimulationConfig,
    Settlement,
    Weather,
)


class ResourceBasedSimulationTest(unittest.TestCase):
    def test_daily_tick_uses_resources_without_currency(self) -> None:
        settlement = create_empty_map_settlement(
            people=3,
            initial_resources={
                "food": 30,
                "water": 30,
                "wood": 10,
                "stone": 5,
            },
            seed=1,
        )

        report = settlement.tick()

        self.assertEqual(settlement.day, 1)
        self.assertNotIn("money", settlement.inventory)
        self.assertNotIn("currency", settlement.inventory)
        self.assertLess(settlement.inventory["food"], 30)
        self.assertLess(settlement.inventory["water"], 30)
        self.assertGreater(report.needs_satisfied_ratio, 0.95)

    def test_weather_changes_renewable_and_water_output(self) -> None:
        solar_definition = BuildingDefinition(
            name="solar_panel",
            daily_outputs={"electricity": 12},
            affected_by_solar=True,
        )
        wind_definition = BuildingDefinition(
            name="wind_turbine",
            daily_outputs={"electricity": 8},
            affected_by_wind=True,
        )
        collector_definition = BuildingDefinition(
            name="rain_cistern",
            daily_outputs={"water": 10},
            affected_by_precipitation=True,
        )
        config = SimulationConfig(
            building_definitions={
                "solar_panel": solar_definition,
                "wind_turbine": wind_definition,
                "rain_cistern": collector_definition,
            }
        )
        cloudy = Settlement(
            people=3,
            inventory={"food": 100, "water": 100},
            buildings=[
                Building("solar_panel"),
                Building("wind_turbine"),
                Building("rain_cistern"),
            ],
            config=config,
            weather=Weather(
                temperature_c=8,
                precipitation_mm=14,
                solar_factor=0.2,
                wind_factor=1.4,
                pressure_system="cyclone",
            ),
        )
        clear = cloudy.clone()
        clear.weather = Weather(
            temperature_c=22,
            precipitation_mm=0,
            solar_factor=1.1,
            wind_factor=0.5,
            pressure_system="anticyclone",
        )

        cloudy.tick()
        clear.tick()

        self.assertGreater(cloudy.inventory["water"], clear.inventory["water"])
        self.assertLess(
            cloudy.inventory["electricity"],
            clear.inventory["electricity"],
        )

    def test_wheel_unlock_increases_daily_logistics_capacity(self) -> None:
        settlement = create_empty_map_settlement(
            people=2,
            initial_resources={"food": 100, "water": 100, "wood": 20, "stone": 20},
            seed=1,
        )

        before = settlement.daily_logistics_capacity
        settlement.unlock_available_technologies()
        self.assertNotIn("wheel", settlement.unlocked_technologies)

        settlement.inventory["plank"] = 4
        settlement.inventory["roundwood"] = 2
        settlement.unlock_available_technologies()

        self.assertIn("wheel", settlement.unlocked_technologies)
        self.assertGreater(settlement.daily_logistics_capacity, before)

    def test_fast_forward_matches_repeated_ticks_for_stable_settlement(self) -> None:
        repeated = Settlement(
            people=4,
            inventory={"food": 500, "water": 500},
            buildings=[
                Building("forager_hut"),
                Building("water_collector"),
            ],
            weather=Weather.stable(),
        )
        projected = repeated.clone()

        reports = [repeated.tick() for _ in range(30)]
        projection = projected.fast_forward(30)

        self.assertEqual(projected.day, repeated.day)
        self.assertAlmostEqual(projected.inventory["food"], repeated.inventory["food"])
        self.assertAlmostEqual(projected.inventory["water"], repeated.inventory["water"])
        self.assertAlmostEqual(
            projection.average_needs_satisfied_ratio,
            sum(report.needs_satisfied_ratio for report in reports) / len(reports),
        )

    def test_resource_recipe_transforms_inputs_without_money(self) -> None:
        sawmill = BuildingDefinition(
            name="sawmill",
            recipes=[
                Recipe(
                    inputs={"wood": 2},
                    outputs={"plank": 3, "sawdust": 1},
                    labor_days=1,
                )
            ],
        )
        settlement = Settlement(
            people=1,
            inventory={"food": 50, "water": 50, "wood": 6},
            buildings=[Building("sawmill")],
            config=SimulationConfig(building_definitions={"sawmill": sawmill}),
            weather=Weather.stable(),
        )

        settlement.tick()

        self.assertNotIn("money", settlement.inventory)
        self.assertEqual(settlement.inventory["plank"], 3)
        self.assertEqual(settlement.inventory["sawdust"], 1)
        self.assertLess(settlement.inventory["wood"], 6)

    def test_seed_adds_repeatable_world_resources(self) -> None:
        first = create_empty_map_settlement(
            people=3,
            initial_resources={"food": 30, "water": 30},
            latitude=45,
            seed=7,
        )
        second = create_empty_map_settlement(
            people=3,
            initial_resources={"food": 30, "water": 30},
            latitude=45,
            seed=7,
        )
        different = create_empty_map_settlement(
            people=3,
            initial_resources={"food": 30, "water": 30},
            latitude=45,
            seed=8,
        )

        self.assertEqual(first.inventory, second.inventory)
        self.assertNotEqual(first.inventory, different.inventory)

    def test_managed_simulation_stops_when_user_enters_zero(self) -> None:
        settlement = create_empty_map_settlement(
            people=3,
            initial_resources={"food": 30, "water": 30},
        )
        output = StringIO()

        reason = run_managed_simulation(
            settlement,
            days=5,
            input_func=lambda _prompt: "0",
            output=output,
        )

        self.assertEqual(settlement.day, 0)
        self.assertIn('командой "0"', reason)
        self.assertIn("Ресурсная стратегия 0.01", output.getvalue())

    def test_managed_simulation_stops_when_everyone_dies(self) -> None:
        settlement = Settlement(
            people=1,
            inventory={},
            buildings=[],
            config=SimulationConfig(unmet_need_health_penalty=1.0),
            weather=Weather.stable(),
            health=0.1,
        )
        output = StringIO()

        reason = run_managed_simulation(
            settlement,
            days=10,
            auto=True,
            output=output,
        )

        self.assertEqual(settlement.people, 0)
        self.assertIn("все жители погибли", reason)
        self.assertIn("Игра окончена", output.getvalue())


if __name__ == "__main__":
    unittest.main()
