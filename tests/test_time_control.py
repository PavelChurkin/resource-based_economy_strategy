import unittest
from typing import Mapping

from game1.time_control import TimeController, TimeMode


class FakeSimulation:
    def __init__(self) -> None:
        self.tick_count = 0
        self.daily_food_delta = -2.0
        self.daily_water_delta = -3.0

    def tick(self) -> Mapping[str, float]:
        self.tick_count += 1
        return {"food": self.daily_food_delta, "water": self.daily_water_delta}

    def daily_summary(self) -> Mapping[str, float]:
        return {"food": self.daily_food_delta, "water": self.daily_water_delta}


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TimeControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sim = FakeSimulation()
        self.clock = FakeClock()
        self.controller = TimeController(simulation=self.sim, clock=self.clock)

    def test_paused_does_not_tick(self) -> None:
        self.clock.advance(60)
        days = self.controller.step()
        self.assertEqual(days, 0)
        self.assertEqual(self.sim.tick_count, 0)

    def test_normal_mode_runs_one_tick_per_10_seconds(self) -> None:
        self.controller.resume(TimeMode.NORMAL)
        self.clock.advance(10)
        self.assertEqual(self.controller.step(), 1)
        self.clock.advance(20)
        self.assertEqual(self.controller.step(), 2)
        self.assertEqual(self.sim.tick_count, 3)
        self.assertEqual(self.controller.day, 3)

    def test_fast_mode_runs_one_tick_per_second(self) -> None:
        self.controller.resume(TimeMode.FAST)
        self.clock.advance(5)
        days = self.controller.step()
        self.assertEqual(days, 5)
        self.assertEqual(self.sim.tick_count, 5)

    def test_fast_forward_does_not_call_tick(self) -> None:
        result = self.controller.fast_forward(30)
        self.assertEqual(self.sim.tick_count, 0)
        self.assertEqual(result.days, 30)
        self.assertAlmostEqual(result.totals["food"], -60.0)
        self.assertAlmostEqual(result.totals["water"], -90.0)
        self.assertEqual(result.started_on_day, 0)
        self.assertEqual(result.ended_on_day, 30)
        self.assertEqual(self.controller.day, 30)

    def test_skip_helpers(self) -> None:
        self.controller.skip_weeks(2)
        self.assertEqual(self.controller.day, 14)
        self.controller.skip_months(1)
        self.assertEqual(self.controller.day, 14 + 28)
        self.controller.skip_years(1)
        self.assertEqual(self.controller.day, 14 + 28 + 336)

    def test_pause_then_resume_does_not_replay_paused_seconds(self) -> None:
        self.controller.resume(TimeMode.NORMAL)
        self.clock.advance(5)
        # Not enough elapsed yet.
        self.assertEqual(self.controller.step(), 0)
        self.controller.pause()
        self.clock.advance(60)  # 60 seconds while paused
        self.controller.resume(TimeMode.NORMAL)
        self.clock.advance(10)
        self.assertEqual(self.controller.step(), 1)
        self.assertEqual(self.sim.tick_count, 1)

    def test_resume_with_paused_mode_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.controller.resume(TimeMode.PAUSED)

    def test_fast_forward_requires_positive_days(self) -> None:
        with self.assertRaises(ValueError):
            self.controller.fast_forward(0)
        with self.assertRaises(ValueError):
            self.controller.fast_forward(-3)


if __name__ == "__main__":
    unittest.main()
