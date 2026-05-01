"""Demonstrate the time controller skipping weeks, months and years.

Run with::

    python examples/run_time_control.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    from game1 import TimeController, TimeMode

    class TinyTownSim:
        """Stand-in for the eventual Settlement simulation."""

        def __init__(self, people: int = 8) -> None:
            self.people = people
            self.food = 200.0
            self.water = 250.0
            self.day = 0

        def tick(self) -> dict[str, float]:
            food_delta = -2.0 * self.people
            water_delta = -2.5 * self.people
            self.food += food_delta
            self.water += water_delta
            self.day += 1
            return {"food": food_delta, "water": water_delta}

        def daily_summary(self) -> dict[str, float]:
            return {"food": -2.0 * self.people, "water": -2.5 * self.people}

    sim = TinyTownSim(people=8)
    controller = TimeController(simulation=sim, clock=time.monotonic)

    print(f"initial: food={sim.food:.1f} water={sim.water:.1f}")

    one_week = controller.skip_weeks(1)
    print(
        f"after 1 week (extrapolated): "
        f"food delta {one_week.totals['food']:+.1f}, "
        f"water delta {one_week.totals['water']:+.1f}, "
        f"day counter now {controller.day}"
    )

    one_year = controller.skip_years(1)
    print(
        f"after 1 year (extrapolated): "
        f"food delta {one_year.totals['food']:+.1f}, "
        f"water delta {one_year.totals['water']:+.1f}, "
        f"day counter now {controller.day}"
    )

    # The simulation itself was never ticked during extrapolation.
    print(f"underlying sim untouched: tick day still {sim.day}")

    # Real-time mode example (FAST = 1 second per game day).
    controller.resume(TimeMode.FAST)
    print("running 3 real seconds in FAST mode (≈ 3 game days)...")
    start = time.monotonic()
    while time.monotonic() - start < 3.0:
        controller.step()
    print(f"sim ticks: {sim.day}, food now {sim.food:.1f}")


if __name__ == "__main__":
    main()
