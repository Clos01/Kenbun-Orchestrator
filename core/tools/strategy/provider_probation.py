"""
Provider Probation & Inferred Account Exhaustion Manager.
=========================================================
Implements long-horizon exponential backoff and calendar probation
for AI API providers that fail due to missing keys, invalid credentials,
or depleted account funds.

Schedule:
  Attempt 1: 5 minutes
  Attempt 2: 1 hour
  Attempt 3: 1 day (24 hours)
  Attempt 4: 1 week (7 days)
  Attempt 5: 1 week + 1 day (8 days)
  Attempt 6: 2 weeks + 1 day (15 days)
  General k >= 4: (k - 3) * 7 + 1 days
"""
import time
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional

from tools.infrastructure.config import settings

logger = logging.getLogger(__name__)

PROBATION_FILE = settings.BRAIN_HEALTH_DIR / "provider_probation.json"


class ProviderProbationManager:
    """
    Tracks failure states and enforces calendar-based long-horizon probation
    to prevent hammering failing/unfunded APIs.
    """

    PERMANENT_ERROR_PATTERNS = [
        "API KEY NOT VALID",
        "INVALID_ARGUMENT",
        "API_KEY_INVALID",
        "BILLING_DISABLED",
        "PERMISSION_DENIED",
        "ACCOUNT_SUSPENDED",
        "CREDIT_EXHAUSTED",
        "RESOURCE_EXHAUSTED",
    ]

    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = state_file or PROBATION_FILE
        self._ensure_state_dir()

    def _ensure_state_dir(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> Dict[str, Any]:
        if not self.state_file.exists():
            return {}
        try:
            with open(self.state_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error reading probation state: {e}")
            return {}

    def _save_state(self, state: Dict[str, Any]):
        try:
            tmp_path = self.state_file.with_suffix(".tmp")
            with open(tmp_path, "w") as f:
                json.dump(state, f, indent=2)
            tmp_path.replace(self.state_file)
        except Exception as e:
            logger.error(f"Error saving probation state: {e}")

    def calculate_cooldown_seconds(self, consecutive_failures: int) -> int:
        """
        Calculates the progressive probation cooldown in seconds.
          k = 1: 5 minutes (300s)
          k = 2: 1 hour (3600s)
          k = 3: 24 hours (86400s, 1 day)
          k = 4: 7 days (604800s, 1 week)
          k = 5: 8 days (691200s, 1 week + 1 day)
          k = 6: 15 days (1296000s, 2 weeks + 1 day)
          k >= 5: (k - 4) * 7 + 1 days
        """
        k = max(1, consecutive_failures)
        if k == 1:
            return 300
        elif k == 2:
            return 3600
        elif k == 3:
            return 86400
        elif k == 4:
            return 7 * 86400
        else:
            days = (k - 4) * 7 + 1
            return days * 86400

    def is_probation_active(self, provider: str = "gemini") -> Tuple[bool, float, Optional[Dict[str, Any]]]:
        """
        Checks if a provider is currently under active probation.
        Returns: (is_active, seconds_remaining, provider_record)
        """
        state = self._load_state()
        record = state.get(provider.lower())
        if not record:
            return False, 0.0, None

        probation_until = record.get("probation_until", 0.0)
        now = time.time()
        remaining = probation_until - now

        if remaining > 0:
            return True, remaining, record

        return False, 0.0, record

    def record_failure(self, provider: str, error_message: str) -> Dict[str, Any]:
        """
        Records a provider failure and calculates the new probation horizon.
        """
        now = time.time()
        err_upper = str(error_message).upper()

        # Determine if this error indicates account exhaustion / invalid key
        is_account_error = any(pat in err_upper for pat in self.PERMANENT_ERROR_PATTERNS)
        inferred_reason = "API Key Invalid or Account Depleted" if is_account_error else "Service Error"

        state = self._load_state()
        p_key = provider.lower()
        record = state.get(p_key, {
            "provider": p_key,
            "consecutive_failures": 0,
            "history": []
        })

        # Increment consecutive failure count
        failures = record.get("consecutive_failures", 0) + 1
        record["consecutive_failures"] = failures

        cooldown_sec = self.calculate_cooldown_seconds(failures)
        probation_until = now + cooldown_sec

        cooldown_days = cooldown_sec / 86400.0
        next_retest_dt = datetime.fromtimestamp(probation_until, tz=timezone.utc)

        record["status"] = "PROBATION"
        record["last_failure_time"] = now
        record["probation_until"] = probation_until
        record["cooldown_seconds"] = cooldown_sec
        record["cooldown_days"] = round(cooldown_days, 2)
        record["next_retest_time_iso"] = next_retest_dt.isoformat()
        record["last_error"] = str(error_message)[:300]
        record["inferred_reason"] = inferred_reason

        state[p_key] = record
        self._save_state(state)

        human_duration = f"{int(cooldown_days)} days" if cooldown_days >= 1 else (f"{int(cooldown_sec // 3600)} hour(s)" if cooldown_sec >= 3600 else f"{int(cooldown_sec // 60)} min")
        print(f"⏸️ [PROBATION ACTIVE] Provider '{provider}' entered probation (Failures: {failures}). Inferred: {inferred_reason}. Next test in {human_duration} ({next_retest_dt.strftime('%Y-%m-%d %H:%M UTC')}).")

        return record

    def record_success(self, provider: str):
        """
        Clears probation when a health check or successful call completes.
        """
        state = self._load_state()
        p_key = provider.lower()
        if p_key in state:
            state[p_key]["status"] = "HEALTHY"
            state[p_key]["consecutive_failures"] = 0
            state[p_key]["probation_until"] = 0.0
            state[p_key]["last_success_time"] = time.time()
            self._save_state(state)
            print(f"✅ [PROBATION CLEARED] Provider '{provider}' restored to HEALTHY status.")

    def reset_probation(self, provider: str):
        """Manual reset for testing or operator intervention."""
        self.record_success(provider)


# Global singleton instance
probation_manager = ProviderProbationManager()
