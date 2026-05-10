import unittest

from game1.sphere_points import FEATURE_MOUNTAIN, build_sphere_point_payload
from game1.time_control import calendar_label
from game1.webgl_planet_viewer import render_webgl_viewer_html
from resource_based_economy_strategy.scenarios import create_player_settlement
from resource_based_economy_strategy.simulation import (
    DAYS_PER_YEAR,
    Building,
    BuildingDefinition,
    Person,
    Settlement,
    SimulationConfig,
    Weather,
)


class Version006GameplayTests(unittest.TestCase):
    def test_player_starts_from_single_city_center_with_adequate_needs(self) -> None:
        settlement = create_player_settlement("Pavel", seed=5)

        self.assertEqual(
            [building.name for building in settlement.buildings],
            ["city_center"],
        )
        self.assertEqual(settlement.buildings[0].point_id, 0)
        self.assertNotIn("wood", settlement.inventory)
        self.assertNotIn("heat", settlement.inventory)
        self.assertGreaterEqual(
            settlement.inventory["food"],
            10 * 0.002 * DAYS_PER_YEAR,
        )
        self.assertGreaterEqual(
            settlement.inventory["water"],
            10 * 0.003 * DAYS_PER_YEAR,
        )

    def test_building_chain_and_single_building_per_point_rules(self) -> None:
        settlement = create_player_settlement("Pavel", seed=7)

        self.assertIn("pump", settlement.available_building_names())
        self.assertIn("farm", settlement.available_building_names())
        self.assertIn("mine", settlement.available_building_names())

        settlement.plan_building("pump", point_id=10)
        with self.assertRaises(ValueError):
            settlement.plan_building("farm", point_id=10)

        with self.assertRaises(ValueError):
            settlement.plan_building(
                "mine",
                point_id=11,
                point_biome="temperate",
                point_features=0,
            )

        mine = settlement.plan_building(
            "mine",
            point_id=12,
            point_biome="mountain",
            point_features=FEATURE_MOUNTAIN,
        )
        self.assertEqual(mine.name, "mine")

    def test_water_shortage_kills_all_unserved_people_in_one_tick(self) -> None:
        people = 4
        settlement = Settlement(
            people=people,
            inventory={"food": 10.0, "water": 0.006},
            buildings=[Building("city_center")],
            citizens=[Person.from_index(index) for index in range(1, people + 1)],
            weather=Weather.stable(),
        )

        report = settlement.tick()

        self.assertEqual(report.deaths, 2)
        self.assertEqual(settlement.people, 2)
        self.assertEqual(
            [person.name for person in settlement.living_citizens()],
            ["Чел1", "Чел2"],
        )
        self.assertEqual(
            [person.death_cause for person in settlement.citizens if not person.alive],
            ["жажды", "жажды"],
        )

    def test_birth_cycle_is_one_child_per_pair_per_eight_months_when_housed(self) -> None:
        settlement = Settlement(
            people=2,
            inventory={"food": 10.0, "water": 10.0},
            buildings=[Building("city_center")],
            citizens=[Person.from_index(1), Person.from_index(2)],
            weather=Weather.stable(),
        )

        report = settlement.fast_forward(8 * 4 * 7)

        self.assertEqual(report.reports[-1].births, 1)
        self.assertEqual(settlement.people, 3)
        self.assertEqual(settlement.citizens[-1].age_years, 0)

    def test_one_adult_activates_only_one_daily_output_building(self) -> None:
        config = SimulationConfig(
            building_definitions={
                "pump": BuildingDefinition(
                    name="pump",
                    daily_outputs={"water": 1.0},
                    vacancies=1,
                ),
                "farm": BuildingDefinition(
                    name="farm",
                    daily_outputs={"food": 1.0},
                    vacancies=1,
                ),
            }
        )
        settlement = Settlement(
            people=1,
            inventory={"food": 1.0, "water": 1.0},
            buildings=[Building("pump"), Building("farm")],
            citizens=[Person.from_index(1)],
            config=config,
            weather=Weather.stable(),
        )

        report = settlement.tick()

        self.assertEqual(report.produced, {"water": 1.0})
        self.assertNotIn("food", report.produced)

    def test_calendar_label_uses_weeks_months_and_years(self) -> None:
        self.assertEqual(calendar_label(0), "Неделя 1 / Месяц 1 / Год 1")
        self.assertEqual(calendar_label(27), "Неделя 4 / Месяц 1 / Год 1")
        self.assertEqual(calendar_label(28), "Неделя 1 / Месяц 2 / Год 1")
        self.assertEqual(calendar_label(336), "Неделя 1 / Месяц 1 / Год 2")


class WebglVersion006UiTests(unittest.TestCase):
    def test_rendered_viewer_contains_version_006_ui_contracts(self) -> None:
        payload = build_sphere_point_payload(counts=(20, 80))

        html = render_webgl_viewer_html(payload)

        self.assertIn("const ZOOM_MAX = 3.2;", html)
        self.assertIn("uniform mat4 uViewMatrix;", html)
        self.assertIn("if (vFacing <= 0.0) discard;", html)
        self.assertIn("gridLayerButton", html)
        self.assertIn("gridOverlay", html)
        self.assertIn("biomeLegend", html)
        self.assertIn("buildingMarkers", html)
        self.assertIn("buildingAtPoint", html)
        self.assertIn("climateSummaryForLatitude", html)
        self.assertIn("energy_mw_day", html)
        self.assertNotIn("древесина", html)


if __name__ == "__main__":
    unittest.main()
