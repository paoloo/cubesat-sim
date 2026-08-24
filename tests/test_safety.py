import unittest

import numpy as np
from cubesec_sim.config import SimulationConfig
from cubesec_sim.safety import validate_safe
from cubesec_sim.seeds import named_rng, rng_pair


class SafetyTests(unittest.TestCase):
    def test_default_config_roundtrip(self):
        cfg = SimulationConfig()
        self.assertEqual(cfg, SimulationConfig.from_dict(cfg.to_dict()))

    def test_rejects_external_and_real_world_values(self):
        bad = [
            {"endpoint": "https://example.invalid"},
            {"device": "/dev/ttyUSB0"},
            {"tle": "1 99999U 00000A"},
            {"latitude": 1.0},
            {"center_frequency": 1.0},
            {"mission_id": "EXTERNAL-1"},
            {"callsign": "ABC123"},
            {"operation": "transmit_frame"},
        ]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_safe(value)

    def test_permits_only_explicitly_synthetic_operation(self):
        validate_safe(
            {
                "operation": "sim_command_inert_bytes",
                "mission_id": "SIM-TEST",
                "callsign": "SIM001",
            }
        )

    def test_seed_streams_are_stable_and_separate(self):
        a_channel, a_policy = rng_pair(10, "cell", 2)
        b_channel, b_policy = rng_pair(10, "cell", 2)
        self.assertTrue(
            np.array_equal(
                a_channel.integers(0, 2**31, 8), b_channel.integers(0, 2**31, 8)
            )
        )
        self.assertTrue(
            np.array_equal(
                a_policy.integers(0, 2**31, 8), b_policy.integers(0, 2**31, 8)
            )
        )
        c_channel, c_policy = rng_pair(10, "cell", 2)
        self.assertFalse(
            np.array_equal(
                c_channel.integers(0, 2**31, 8), c_policy.integers(0, 2**31, 8)
            )
        )

    def test_named_policy_streams_are_order_independent(self):
        a1 = named_rng(7, "cell", 1, "policy-a").integers(0, 1000, 10)
        _ = named_rng(7, "cell", 1, "policy-b").integers(0, 1000, 10)
        a2 = named_rng(7, "cell", 1, "policy-a").integers(0, 1000, 10)
        self.assertTrue(np.array_equal(a1, a2))


if __name__ == "__main__":
    unittest.main()
