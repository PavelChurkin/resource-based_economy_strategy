"""Climate model with cyclones / anticyclones for the polygonal planet.

Issue #3 explicitly calls for cyclones and anticyclones with periodic
behaviour: a cyclone reduces solar generation but raises rainfall, while a
shift between systems boosts wind.

This module produces deterministic per-tile weather as a function of day
number and tile latitude/elevation. No external dependencies are used so the
output is reproducible across machines and Python versions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import sin, cos, radians, pi
from typing import Mapping


class PressureSystem(str, Enum):
    CYCLONE = "cyclone"
    ANTICYCLONE = "anticyclone"
    TRANSITION = "transition"


@dataclass(frozen=True)
class TileWeather:
    """Per-tile, per-day weather snapshot."""

    day: int
    latitude: float
    pressure: PressureSystem
    temperature_c: float
    rainfall_mm: float
    solar_factor: float
    wind_factor: float
    hydropower_factor: float

    def yields(self) -> Mapping[str, float]:
        """Return generation multipliers grouped by source kind."""

        return {
            "solar": self.solar_factor,
            "wind": self.wind_factor,
            "hydro": self.hydropower_factor,
            "rain": self.rainfall_mm,
        }


@dataclass
class Climate:
    """Deterministic climate generator.

    The seasonal cycle uses a sine wave over a year of ``year_length_days``
    days. Cyclones move on a longer cycle (``pressure_period_days``) so the
    same tile alternates between high and low pressure systems through the
    year.
    """

    year_length_days: int = 360
    pressure_period_days: int = 12
    base_temperature_c: float = 15.0
    seasonal_amplitude_c: float = 18.0

    def pressure_for(self, day: int, latitude: float) -> PressureSystem:
        # Latitude shifts the phase so opposite hemispheres alternate.
        phase = (day + int(latitude) % self.pressure_period_days)
        slot = phase % self.pressure_period_days
        third = self.pressure_period_days // 3 or 1
        if slot < third:
            return PressureSystem.CYCLONE
        if slot < 2 * third:
            return PressureSystem.TRANSITION
        return PressureSystem.ANTICYCLONE

    def seasonal_temperature(self, day: int, latitude: float) -> float:
        # Northern summer when day fraction ~0.25, southern summer ~0.75.
        year_fraction = (day % self.year_length_days) / self.year_length_days
        seasonal = sin(2 * pi * (year_fraction - 0.25))
        latitude_factor = sin(radians(latitude))
        # Equatorial warmth, polar cold; modulated by season.
        latitude_band = self.base_temperature_c * cos(radians(latitude))
        return latitude_band + self.seasonal_amplitude_c * seasonal * latitude_factor

    def weather_for(
        self,
        day: int,
        latitude: float,
        solar_baseline: float,
        wind_baseline: float,
        elevation_m: float = 0.0,
    ) -> TileWeather:
        pressure = self.pressure_for(day, latitude)
        temperature = self.seasonal_temperature(day, latitude)
        # Adiabatic lapse rate ~6.5 C / km.
        temperature -= elevation_m / 1000.0 * 6.5

        if pressure is PressureSystem.CYCLONE:
            solar = solar_baseline * 0.45
            wind = min(1.0, wind_baseline * 1.1)
            rainfall = 14.0
            hydropower = 1.25
        elif pressure is PressureSystem.ANTICYCLONE:
            solar = solar_baseline * 1.1
            wind = wind_baseline * 0.7
            rainfall = 1.5
            hydropower = 0.85
        else:
            solar = solar_baseline * 0.9
            wind = min(1.0, wind_baseline * 1.4)  # transition boosts wind
            rainfall = 6.0
            hydropower = 1.0

        # Cap factors at sensible bounds.
        solar = max(0.0, min(1.2, solar))
        wind = max(0.0, min(1.2, wind))
        return TileWeather(
            day=day,
            latitude=latitude,
            pressure=pressure,
            temperature_c=round(temperature, 2),
            rainfall_mm=rainfall,
            solar_factor=round(solar, 3),
            wind_factor=round(wind, 3),
            hydropower_factor=round(hydropower, 3),
        )
