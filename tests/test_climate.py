import unittest

from game1.climate import Climate, PressureSystem


class ClimateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.climate = Climate()

    def test_pressure_cycle_visits_all_systems(self) -> None:
        seen = {self.climate.pressure_for(day, latitude=0) for day in range(60)}
        self.assertIn(PressureSystem.CYCLONE, seen)
        self.assertIn(PressureSystem.ANTICYCLONE, seen)
        self.assertIn(PressureSystem.TRANSITION, seen)

    def test_cyclone_reduces_solar_and_raises_rainfall(self) -> None:
        # Find a cyclone day deterministically.
        for day in range(60):
            if self.climate.pressure_for(day, latitude=0) is PressureSystem.CYCLONE:
                cyclone_day = day
                break
        else:
            self.fail("no cyclone day found in 60-day window at equator")

        cyclone = self.climate.weather_for(
            cyclone_day, latitude=0, solar_baseline=1.0, wind_baseline=0.5
        )

        for day in range(60):
            if self.climate.pressure_for(day, latitude=0) is PressureSystem.ANTICYCLONE:
                anticyclone_day = day
                break
        else:
            self.fail("no anticyclone day found in 60-day window at equator")

        anticyclone = self.climate.weather_for(
            anticyclone_day, latitude=0, solar_baseline=1.0, wind_baseline=0.5
        )

        self.assertLess(cyclone.solar_factor, anticyclone.solar_factor)
        self.assertGreater(cyclone.rainfall_mm, anticyclone.rainfall_mm)
        self.assertGreater(cyclone.hydropower_factor, anticyclone.hydropower_factor)

    def test_transition_boosts_wind(self) -> None:
        for day in range(60):
            if self.climate.pressure_for(day, latitude=0) is PressureSystem.TRANSITION:
                weather = self.climate.weather_for(
                    day, latitude=0, solar_baseline=1.0, wind_baseline=0.5
                )
                # 0.5 baseline * 1.4 boost = 0.7 (capped at 1.2)
                self.assertGreaterEqual(weather.wind_factor, 0.6)
                return
        self.fail("no transition day found in 60-day window at equator")

    def test_elevation_lowers_temperature(self) -> None:
        sea_level = self.climate.weather_for(
            0, latitude=30, solar_baseline=1.0, wind_baseline=0.5, elevation_m=0
        )
        mountain = self.climate.weather_for(
            0, latitude=30, solar_baseline=1.0, wind_baseline=0.5, elevation_m=2000
        )
        # 2000 m * 6.5 / 1000 = 13 C lapse
        self.assertAlmostEqual(
            sea_level.temperature_c - mountain.temperature_c, 13.0, places=2
        )

    def test_seasonal_cycle_is_periodic(self) -> None:
        a = self.climate.seasonal_temperature(0, latitude=45)
        b = self.climate.seasonal_temperature(self.climate.year_length_days, latitude=45)
        self.assertAlmostEqual(a, b, places=6)


if __name__ == "__main__":
    unittest.main()
