import unittest

from game1.time_control import TimeController, TimeMode
from resource_based_economy_strategy.scenarios import create_player_settlement
from resource_based_economy_strategy.simulation import (
    Building,
    Person,
    Settlement,
    Weather,
    policy_color,
)
from game1.webgl_planet_viewer import render_webgl_viewer_html
from game1.sphere_points import build_sphere_point_payload


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeSimulation:
    def __init__(self) -> None:
        self.ticks = 0

    def tick(self) -> dict[str, float]:
        self.ticks += 1
        return {}

    def daily_summary(self) -> dict[str, float]:
        return {}


class Version005GameplayTests(unittest.TestCase):
    def test_weekly_time_controller_runs_seven_days_every_five_seconds(self) -> None:
        clock = FakeClock()
        sim = FakeSimulation()
        controller = TimeController.weekly(simulation=sim, clock=clock)

        controller.resume(TimeMode.NORMAL)
        clock.advance(4.9)
        self.assertEqual(controller.step(), 0)

        clock.advance(0.1)
        self.assertEqual(controller.step(), 7)
        self.assertEqual(sim.ticks, 7)
        self.assertEqual(controller.day, 7)

    def test_starting_player_has_ten_people_and_year_supplies(self) -> None:
        settlement = create_player_settlement("Pavel", seed=5)

        self.assertEqual(settlement.player_nickname, "Pavel")
        self.assertEqual(settlement.people, 10)
        self.assertEqual(len(settlement.living_citizens()), 10)
        self.assertTrue(all(person.is_adult for person in settlement.living_citizens()))
        self.assertGreaterEqual(settlement.inventory["food"], 10 * 1.8 * 360)
        self.assertGreaterEqual(settlement.inventory["water"], 10 * 3.0 * 360)

    def test_children_do_not_count_as_workers(self) -> None:
        settlement = Settlement(
            people=2,
            inventory={"food": 500, "water": 500},
            buildings=[Building("quarry")],
            citizens=[
                Person.from_index(1, age_years=30),
                Person.from_index(2, age_years=8),
            ],
            weather=Weather.stable(),
        )

        demographics = settlement.demographics()

        self.assertEqual(demographics.adults, 1)
        self.assertEqual(demographics.children, 1)
        self.assertEqual(demographics.vacancies, 3)
        self.assertEqual(demographics.unemployed, 0)
        self.assertEqual(settlement.daily_labor_capacity, 1.0)

    def test_tick_week_advances_seven_daily_reports_and_records_events(self) -> None:
        settlement = create_player_settlement("Pavel", seed=6)

        report = settlement.tick_week()

        self.assertEqual(report.days, 7)
        self.assertEqual(settlement.day, 7)
        self.assertEqual(len(report.reports), 7)
        self.assertTrue(settlement.status_events)

    def test_building_menu_unlocks_lumberjack_after_stone_quarry(self) -> None:
        settlement = create_player_settlement("Pavel", seed=7)

        self.assertIn("stone_quarry", settlement.available_building_names())
        self.assertNotIn("lumberjack_site", settlement.available_building_names())

        settlement.plan_building("stone_quarry", point_id=123)

        self.assertIn("lumberjack_site", settlement.available_building_names())
        self.assertEqual(settlement.buildings[-1].point_id, 123)

    def test_policy_colors_match_issue_palette(self) -> None:
        self.assertEqual(policy_color("own"), "#2fb344")
        self.assertEqual(policy_color("neutral"), "#2f80ed")
        self.assertEqual(policy_color("enemy"), "#d63031")
        self.assertEqual(policy_color("ally"), "#f2c94c")


class WebglGameUiTests(unittest.TestCase):
    def test_rendered_viewer_contains_game_ui_controls(self) -> None:
        payload = build_sphere_point_payload(counts=(20, 80))

        html = render_webgl_viewer_html(payload)

        self.assertIn("nicknameInput", html)
        self.assertIn("pauseButton", html)
        self.assertIn("selectedPointPanel", html)
        self.assertIn("buildingMenu", html)
        self.assertIn("gameState", html)
        self.assertIn("tick every 5 seconds", html)


if __name__ == "__main__":
    unittest.main()
