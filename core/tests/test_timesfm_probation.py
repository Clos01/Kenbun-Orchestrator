"""
Unit Test Suite for TimesFM 3 Multivariate Forecaster & Calendar Probation Manager.
==================================================================================
Tests:
  1. Progressive calendar cooldown schedule:
     - 1st failure: 5 minutes
     - 2nd failure: 1 hour
     - 3rd failure: 1 day (24 hours)
     - 4th failure: 7 days (1 week)
     - 5th failure: 8 days (1 week + 1 day)
     - 6th failure: 15 days (2 weeks + 1 day)
  2. Provider account exhaustion inference (invalid keys, billing disabled, quota exhausted).
  3. TimesFM 3 multivariate time-series projection and Bayesian prior modulation.
  4. MAB candidate model arm filtering (auto-fallback to 'local' when cloud is on probation).
  5. Thompson sampling score suppression for tools on probation.
  6. Gemini reviewer short-circuiting and graceful local supervisor failover.
"""
import time
import tempfile
from pathlib import Path
import unittest

from tools.strategy.provider_probation import ProviderProbationManager
from tools.strategy.timesfm_forecaster import TimesFMForecaster
from tools.strategy.decision_logic import ContextualModelBandit, DecisionRouter
from tools.utils.bayesian import rank_tools_thompson


class TestProviderProbationManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "probation_test.json"
        self.manager = ProviderProbationManager(state_file=self.state_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_progressive_calendar_cooldown_schedule(self):
        """Verify the exact calendar progression required by the operator."""
        # k=1: 5m (300s)
        self.assertEqual(self.manager.calculate_cooldown_seconds(1), 300)
        # k=2: 1h (3600s)
        self.assertEqual(self.manager.calculate_cooldown_seconds(2), 3600)
        # k=3: 1 day (86400s)
        self.assertEqual(self.manager.calculate_cooldown_seconds(3), 86400)
        # k=4: 1 week (7 days = 604800s)
        self.assertEqual(self.manager.calculate_cooldown_seconds(4), 7 * 86400)
        # k=5: 1 week + 1 day (8 days = 691200s)
        self.assertEqual(self.manager.calculate_cooldown_seconds(5), 8 * 86400)
        # k=6: 2 weeks + 1 day (15 days = 1296000s)
        self.assertEqual(self.manager.calculate_cooldown_seconds(6), 15 * 86400)
        # k=7: 3 weeks + 1 day (22 days = 1900800s)
        self.assertEqual(self.manager.calculate_cooldown_seconds(7), 22 * 86400)

    def test_account_exhaustion_inference(self):
        """Verify that permanent API key / quota errors are inferred accurately."""
        rec = self.manager.record_failure("gemini", "400 INVALID_ARGUMENT: API key not valid. Please pass a valid API key.")
        self.assertEqual(rec["status"], "PROBATION")
        self.assertEqual(rec["consecutive_failures"], 1)
        self.assertEqual(rec["inferred_reason"], "API Key Invalid or Account Depleted")
        self.assertTrue(self.manager.is_probation_active("gemini")[0])

    def test_repeated_failure_progression(self):
        """Verify that consecutive failures advance through the week and week+1day schedule."""
        for i in range(1, 6):
            rec = self.manager.record_failure("gemini", "RESOURCE_EXHAUSTED quota exceeded")
        self.assertEqual(rec["consecutive_failures"], 5)
        self.assertEqual(rec["cooldown_days"], 8.0)  # 1 week + 1 day
        self.assertTrue(self.manager.is_probation_active("gemini")[0])

    def test_probation_success_clearing(self):
        """Verify that when a test call succeeds, probation is restored to HEALTHY."""
        self.manager.record_failure("gemini", "400 INVALID_ARGUMENT")
        self.assertTrue(self.manager.is_probation_active("gemini")[0])
        
        self.manager.record_success("gemini")
        is_active, _, rec = self.manager.is_probation_active("gemini")
        self.assertFalse(is_active)
        self.assertEqual(rec["status"], "HEALTHY")
        self.assertEqual(rec["consecutive_failures"], 0)


class TestTimesFMForecaster(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.telemetry_file = Path(self.temp_dir.name) / "timesfm_test.json"
        self.forecaster = TimesFMForecaster(telemetry_file=self.telemetry_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cold_start_forecast(self):
        """Unobserved tools/models should return healthy baseline forecasts."""
        forecast = self.forecaster.forecast_health("ask_architect")
        self.assertEqual(forecast.trend, "HEALTHY")
        self.assertFalse(forecast.is_probation_suppressed)
        self.assertEqual(forecast.recommendation, "PROCEED")

    def test_multivariate_degradation_forecast(self):
        """Repeated high-latency failures should trigger DEGRADING or CRITICAL trend."""
        for _ in range(8):
            self.forecaster.record_telemetry("custom_tool", success=False, latency=12.5, cost=0.01, error_msg="Timeout")
        
        forecast = self.forecaster.forecast_health("custom_tool")
        self.assertGreater(forecast.predicted_failure_probability, 0.5)
        self.assertIn(forecast.trend, ["DEGRADING", "CRITICAL"])
        self.assertIn(forecast.recommendation, ["DEGRADE", "AVOID", "FALLBACK_LOCAL"])

    def test_bayesian_prior_modulation(self):
        """TimesFM should modulate Beta(alpha, beta) parameters based on failure forecast."""
        # Tool with 5 failures in a row
        for _ in range(5):
            self.forecaster.record_telemetry("unstable_tool", success=False, latency=8.0, cost=0.0)
        
        mod_alpha, mod_beta, p_fail = self.forecaster.modulate_bayesian_prior("unstable_tool", "global", 5.0, 2.0)
        self.assertGreater(p_fail, 0.4)
        self.assertLess(mod_alpha, 5.0)
        self.assertGreater(mod_beta, 2.0)


class TestBanditAndBayesianRoutingIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.stats_path = Path(self.temp_dir.name) / "mab_stats.json"
        self.bandit = ContextualModelBandit(self.stats_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_filter_candidate_models_when_gemini_under_probation(self):
        """When Gemini is on probation, all Gemini arms must be pruned and 'local' must be chosen."""
        from tools.strategy.provider_probation import probation_manager
        # Put gemini on probation
        probation_manager.record_failure("gemini", "API key not valid")
        try:
            arm = self.bandit.select_arm("SIMPLE")
            self.assertEqual(arm, "local")
            arm_complex = self.bandit.select_arm("COMPLEX")
            self.assertEqual(arm_complex, "local")
        finally:
            probation_manager.reset_probation("gemini")

    def test_thompson_sampling_suppression_under_probation(self):
        """When Gemini is on probation, Gemini-backed tools should be ranked at the bottom."""
        from tools.strategy.provider_probation import probation_manager
        probation_manager.record_failure("gemini", "400 INVALID_ARGUMENT: API key not valid")
        try:
            candidates = ["review_code_with_gemini", "save_checkpoint", "run_code_safely"]
            ranked = rank_tools_thompson("global", candidates, exploration_mode=False)
            ordered_tools = [t for t, _ in ranked]
            # review_code_with_gemini must be pushed to the very bottom
            self.assertEqual(ordered_tools[-1], "review_code_with_gemini")
            self.assertIn(ordered_tools[0], ["save_checkpoint", "run_code_safely"])
        finally:
            probation_manager.reset_probation("gemini")


if __name__ == "__main__":
    unittest.main()
