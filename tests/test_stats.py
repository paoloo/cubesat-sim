import unittest

from cubesec_sim.stats import mcnemar_exact, paired_bootstrap_difference, wilson


class StatsTests(unittest.TestCase):
    def test_wilson_bounds(self):
        low, high = wilson(80, 80)
        self.assertAlmostEqual(low, 0.954180, places=5)
        self.assertEqual(high, 1.0)

    def test_mcnemar_and_bootstrap(self):
        result = mcnemar_exact([True, True, False, True], [False, True, True, False])
        self.assertEqual(result["baseline_only"], 2)
        self.assertEqual(result["candidate_only"], 1)
        boot = paired_bootstrap_difference([1, 1, 0], [0, 1, 1], seed=1, draws=100)
        self.assertIn("ci_low", boot)


if __name__ == "__main__":
    unittest.main()
