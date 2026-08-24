import unittest

import numpy as np
from cubesec_sim.geometry import (
    doppler_at_fraction,
    doppler_profile,
    elevation_profile,
    slant_range_km,
    snr_at_fraction,
    snr_profile,
)


class GeometryTests(unittest.TestCase):
    def test_range_is_altitude_at_zenith_and_larger_at_horizon(self):
        ranges = slant_range_km(np.array([0.0, 90.0]), altitude_km=550.0)
        self.assertGreater(ranges[0], ranges[1])
        self.assertAlmostEqual(ranges[1], 550.0, places=8)

    def test_profiles_are_symmetric_and_bounded(self):
        elevation = elevation_profile(101)
        snr = snr_profile(101, 10.0)
        doppler = doppler_profile(101, 0.003)
        self.assertTrue(np.allclose(elevation, elevation[::-1]))
        self.assertTrue(np.allclose(snr, snr[::-1]))
        self.assertLessEqual(np.max(np.abs(doppler)), 0.0030000001)
        self.assertAlmostEqual(doppler[0], -doppler[-1], places=8)

    def test_local_pass_values_have_expected_order_and_sign(self):
        self.assertGreater(snr_at_fraction(0.5, 10.0), snr_at_fraction(0.05, 10.0))
        self.assertGreater(doppler_at_fraction(0.1, 0.003), 0.0)
        self.assertLess(doppler_at_fraction(0.9, 0.003), 0.0)


if __name__ == "__main__":
    unittest.main()
