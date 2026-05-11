import unittest

from game1.sphere_points import build_sphere_point_payload
from game1.time_control import calendar_label
from game1.webgl_planet_viewer import render_webgl_viewer_html
from resource_based_economy_strategy.scenarios import create_player_settlement
from resource_based_economy_strategy.simulation import (
    DAYS_PER_YEAR,
    Building,
    Person,
    Settlement,
    Weather,
)


class Version007GameplayTests(unittest.TestCase):
    def test_city_center_can_be_placed_by_player_before_other_buildings(self) -> None:
        settlement = create_player_settlement("Pavel", city_center_point_id=None)

        self.assertEqual(settlement.buildings, [])
        self.assertEqual(settlement.available_building_names(), ["city_center"])
        with self.assertRaises(ValueError):
            settlement.plan_building("pump", point_id=10, point_biome="temperate")

        center = settlement.plan_building(
            "city_center",
            point_id=42,
            point_biome="temperate",
        )

        self.assertEqual(center.point_id, 42)
        self.assertIn("pump", settlement.available_building_names())

    def test_ocean_points_reject_all_buildings(self) -> None:
        settlement = create_player_settlement("Pavel", city_center_point_id=None)

        with self.assertRaisesRegex(ValueError, "ocean"):
            settlement.plan_building(
                "city_center",
                point_id=3,
                point_biome="ocean",
            )

    def test_concrete_factory_uses_bricks_to_build_and_sand_ore_to_produce(self) -> None:
        settlement = create_player_settlement("Pavel")
        settlement.inventory.update(
            {
                "brick": 20.0,
                "stone": 20.0,
                "sand": 10.0,
                "raw_metal": 10.0,
                "food": 20.0,
                "water": 20.0,
            }
        )
        settlement.buildings.append(Building("quarry", point_id=10))
        settlement.buildings.append(Building("brick_factory", point_id=11))

        factory = settlement.plan_building(
            "concrete_factory",
            point_id=12,
            point_biome="temperate",
        )
        report = settlement.tick()

        self.assertEqual(factory.name, "concrete_factory")
        self.assertGreater(report.transformed["concrete"], 0.0)
        self.assertLess(settlement.inventory["sand"], 10.0)
        self.assertLess(settlement.inventory["raw_metal"], 10.0)

    def test_children_consume_half_food_and_water_and_grow_up(self) -> None:
        child = Person.from_index(2, age_years=15)
        child.age_days = 16 * DAYS_PER_YEAR - 1
        settlement = Settlement(
            people=2,
            inventory={"food": 0.003, "water": 0.0045},
            buildings=[Building("city_center")],
            citizens=[Person.from_index(1), child],
            weather=Weather.stable(),
        )

        report = settlement.tick()

        self.assertEqual(report.deaths, 0)
        self.assertAlmostEqual(report.consumed["food"], 0.003)
        self.assertAlmostEqual(report.consumed["water"], 0.0045)
        self.assertTrue(child.is_adult)
        self.assertIn("Чел2 #0002 взрослеет.", report.status_events)

    def test_active_buildings_assign_named_workers_and_can_be_demolished(self) -> None:
        pump = Building("pump", point_id=1)
        farm = Building("farm", point_id=2)
        settlement = Settlement(
            people=1,
            inventory={"food": 5.0, "water": 5.0},
            buildings=[pump, farm],
            citizens=[Person.from_index(1)],
            weather=Weather.stable(),
        )

        report = settlement.tick()

        self.assertIn("water", report.produced)
        self.assertNotIn("food", report.produced)
        self.assertEqual(settlement.worker_names_for(pump), ["Чел1"])
        self.assertEqual(settlement.worker_names_for(farm), [])

        settlement.set_building_active(pump, False)
        settlement.demolish_building(farm)

        self.assertFalse(pump.active)
        self.assertNotIn(farm, settlement.buildings)

    def test_calendar_label_includes_absolute_week_in_parentheses(self) -> None:
        self.assertEqual(calendar_label(0), "Неделя 1 (1) / Месяц 1 / Год 1")
        self.assertEqual(calendar_label(336), "Неделя 1 (49) / Месяц 1 / Год 2")


class WebglVersion007UiTests(unittest.TestCase):
    def test_rendered_viewer_contains_version_007_ui_contracts(self) -> None:
        payload = build_sphere_point_payload(counts=(20, 80))

        html = render_webgl_viewer_html(payload)

        self.assertIn("selectedPointMarker", html)
        self.assertIn("buildingUnavailableReason", html)
        self.assertIn("alert(message);", html)
        self.assertIn("skipMonthButton", html)
        self.assertIn("skipYearButton", html)
        self.assertIn("resourceTrend", html)
        self.assertIn("concrete_factory", html)
        self.assertIn("childrenAgeWeeks", html)
        self.assertIn("const POINTER_ROTATE_STEP = 0.0035;", html)
        self.assertIn("return value;", html)
        self.assertIn("buildings: [],", html)
        self.assertNotIn('<h2>Политика</h2>', html)
        self.assertNotIn("policyPanel", html)
        self.assertNotIn('{ id: "city_center", pointId: 0', html)


if __name__ == "__main__":
    unittest.main()
