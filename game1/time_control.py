"""Time controller with pause, speed and fast-forward extrapolation.

Issue #3 describes four time modes:

- *paused* — the simulation does not advance,
- *normal* — one game day takes about 10 seconds of wall-clock time,
- *fast* — one game day takes about 1 second of wall-clock time,
- *skip* — weeks, months or years are summarised by extrapolating known
  per-day statistics rather than running a full tick per day.

This module exposes a ``TimeController`` that wraps an arbitrary simulation
exposing two operations:

- ``tick()`` advances the simulation by exactly one day,
- ``daily_summary()`` returns a mapping of statistic name to per-day value.

The controller uses an injectable ``clock`` callable so tests can step time
without sleeping. A real client passes ``time.monotonic``.

Version 0.0.5 keeps those defaults for compatibility and adds
``TimeController.weekly(...)``: normal mode advances one game week
(seven daily simulation ticks) every five wall-clock seconds, matching the
new game-loop requirement while still allowing planning during pause.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Mapping, Protocol


class TimeMode(str, Enum):
    PAUSED = "paused"
    NORMAL = "normal"
    FAST = "fast"
    SKIP = "skip"


class TickableSimulation(Protocol):
    def tick(self) -> Mapping[str, float]: ...
    def daily_summary(self) -> Mapping[str, float]: ...


@dataclass
class ExtrapolationResult:
    days: int
    totals: dict[str, float]
    started_on_day: int
    ended_on_day: int


@dataclass
class TimeController:
    simulation: TickableSimulation
    clock: Callable[[], float]
    seconds_per_day_normal: float = 10.0
    seconds_per_day_fast: float = 1.0
    game_days_per_tick: int = 1
    mode: TimeMode = TimeMode.PAUSED
    day: int = 0
    _last_tick_time: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        if self.game_days_per_tick < 1:
            raise ValueError("game_days_per_tick must be positive")
        self._last_tick_time = self.clock()

    @classmethod
    def weekly(
        cls,
        simulation: TickableSimulation,
        clock: Callable[[], float],
    ) -> TimeController:
        """Build the v0.0.5 clock: one week every five seconds."""

        return cls(
            simulation=simulation,
            clock=clock,
            seconds_per_day_normal=5.0,
            seconds_per_day_fast=1.0,
            game_days_per_tick=7,
        )

    # ------------------------------------------------------------------
    # Mode control
    # ------------------------------------------------------------------
    def pause(self) -> None:
        self.mode = TimeMode.PAUSED

    def resume(self, mode: TimeMode = TimeMode.NORMAL) -> None:
        if mode is TimeMode.PAUSED:
            raise ValueError("use pause() to pause the simulation")
        self.mode = mode
        self._last_tick_time = self.clock()

    # ------------------------------------------------------------------
    # Real-time stepping
    # ------------------------------------------------------------------
    def _seconds_per_day(self) -> float:
        if self.mode is TimeMode.NORMAL:
            return self.seconds_per_day_normal
        if self.mode is TimeMode.FAST:
            return self.seconds_per_day_fast
        raise RuntimeError(f"no real-time rate for mode {self.mode}")

    def step(self) -> int:
        """Run ticks corresponding to elapsed wall-clock time.

        Returns the number of full days advanced. In ``PAUSED`` and ``SKIP``
        modes this is always zero — callers use :meth:`fast_forward` for
        bulk-time progression.
        """

        if self.mode in (TimeMode.PAUSED, TimeMode.SKIP):
            return 0

        now = self.clock()
        elapsed = now - self._last_tick_time
        seconds_per_day = self._seconds_per_day()
        if elapsed < seconds_per_day:
            return 0
        ticks_to_run = int(elapsed // seconds_per_day)
        days_to_run = ticks_to_run * self.game_days_per_tick
        for _ in range(days_to_run):
            self.simulation.tick()
            self.day += 1
        self._last_tick_time += ticks_to_run * seconds_per_day
        return days_to_run

    # ------------------------------------------------------------------
    # Skip mode: extrapolate without iterating per-day
    # ------------------------------------------------------------------
    def fast_forward(self, days: int) -> ExtrapolationResult:
        """Skip ``days`` days using per-day statistics extrapolation.

        This mirrors the issue's requirement for skipping weeks, months and
        years. The simulation's current ``daily_summary()`` is multiplied by
        ``days`` to estimate cumulative resource changes without paying the
        per-tick cost. The internal day counter advances accordingly.
        """

        if days <= 0:
            raise ValueError("days must be positive")
        previous_mode = self.mode
        self.mode = TimeMode.SKIP
        try:
            summary = self.simulation.daily_summary()
            totals = {key: float(value) * days for key, value in summary.items()}
            started_on = self.day
            self.day += days
            return ExtrapolationResult(
                days=days,
                totals=totals,
                started_on_day=started_on,
                ended_on_day=self.day,
            )
        finally:
            self.mode = previous_mode
            self._last_tick_time = self.clock()

    def skip_weeks(self, weeks: int) -> ExtrapolationResult:
        return self.fast_forward(weeks * 7)

    def skip_months(self, months: int, days_per_month: int = 30) -> ExtrapolationResult:
        return self.fast_forward(months * days_per_month)

    def skip_years(self, years: int, days_per_year: int = 360) -> ExtrapolationResult:
        return self.fast_forward(years * days_per_year)
