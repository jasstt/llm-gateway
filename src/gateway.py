"""
gateway.py — Ana proxy. Tüm istekler buradan geçer.
Pipeline: rate_limiter → budget → circuit_breaker (fallback içinde) → provider → telemetry
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.rate_limiter import RateLimiter, RateLimitExceeded
from src.budget import BudgetManager, BudgetExceeded
from src.fallback import FallbackRouter, FallbackExhausted
from src.telemetry import Telemetry
from src.providers.base import ProviderResponse


class GatewayResponse:
    """Gateway'den dönen standart yanıt nesnesi."""

    def __init__(
        self,
        success: bool,
        text: str = "",
        status_code: int = 200,
        error: str = "",
        log_record: dict = None,
    ):
        self.success = success
        self.text = text
        self.status_code = status_code
        self.error = error
        self.log_record = log_record or {}

    def __repr__(self):
        if self.success:
            return (
                f"GatewayResponse(✓ {self.status_code} | "
                f"{self.log_record.get('provider','')} | "
                f"tokens={self.log_record.get('total_tokens',0)} | "
                f"cost=${self.log_record.get('cost_usd',0):.6f} | "
                f"latency={self.log_record.get('latency_ms',0):.0f}ms)"
            )
        return f"GatewayResponse(✗ {self.status_code} | {self.error})"


class Gateway:
    """
    LLM Gateway — tek giriş noktası.

    Kullanım:
        gw = Gateway()
        result = gw.complete(prompt="Merhaba!", user_id="u1", team_id="team_alpha")
    """

    def __init__(self):
        self._rate_limiter = RateLimiter()
        self._budget = BudgetManager()
        self._router = FallbackRouter()
        self._telemetry = Telemetry()

    def complete(
        self,
        prompt: str,
        user_id: str = "anonymous",
        team_id: str = "unknown",
        ip: str = "127.0.0.1",
    ) -> GatewayResponse:
        """
        Prompt'u pipeline'dan geçirir ve yanıt döner.

        Pipeline adımları:
          1. Rate Limiter — 429 RateLimitExceeded
          2. Budget — 402 BudgetExceeded
          3. Fallback Router (circuit breaker içerir) — provider çağrısı
          4. Bütçe düşümü (başarılıysa)
          5. Telemetry log
        """

        # ─── 1. Rate Limiting ───────────────────────────────────────────
        try:
            self._rate_limiter.check(user_id=user_id, ip=ip)
        except RateLimitExceeded as e:
            _fake_resp = _make_error_response("rate_limit", str(e))
            self._telemetry.log(user_id, team_id, prompt, _fake_resp)
            return GatewayResponse(
                success=False,
                status_code=429,
                error=str(e),
                log_record={"error_type": "RateLimitExceeded"},
            )

        # ─── 2. Budget Check ────────────────────────────────────────────
        try:
            self._budget.check_and_reserve(team_id)
        except BudgetExceeded as e:
            _fake_resp = _make_error_response("budget_exceeded", str(e))
            self._telemetry.log(user_id, team_id, prompt, _fake_resp)
            return GatewayResponse(
                success=False,
                status_code=402,
                error=str(e),
                log_record={"error_type": "BudgetExceeded"},
            )

        # ─── 3. Provider (Fallback + Circuit Breaker) ───────────────────
        try:
            response: ProviderResponse = self._router.complete(prompt, user_id)
        except FallbackExhausted as e:
            _fake_resp = _make_error_response("fallback_exhausted", str(e))
            log = self._telemetry.log(user_id, team_id, prompt, _fake_resp)
            return GatewayResponse(
                success=False,
                status_code=502,
                error=str(e),
                log_record=log,
            )

        # ─── 4. Budget Deduction ────────────────────────────────────────
        if response.success:
            self._budget.deduct(team_id, response.cost_usd)

        # ─── 5. Telemetry ───────────────────────────────────────────────
        log = self._telemetry.log(user_id, team_id, prompt, response)

        if response.success:
            return GatewayResponse(
                success=True,
                text=response.text,
                status_code=200,
                log_record=log,
            )
        else:
            return GatewayResponse(
                success=False,
                status_code=500,
                error=f"{response.error_type}: {response.error_message}",
                log_record=log,
            )

    def get_budget_status(self, team_id: str) -> dict:
        return self._budget.get_status(team_id)

    def get_telemetry_stats(self) -> dict:
        return self._telemetry.get_stats()

    def get_rate_limit_stats(self, user_id: str, ip: str = "127.0.0.1") -> dict:
        return self._rate_limiter.get_stats(user_id, ip)


def _make_error_response(error_type: str, message: str) -> ProviderResponse:
    """Rate limit / budget hataları için sahte bir ProviderResponse oluşturur."""
    return ProviderResponse(
        success=False,
        text="",
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        latency_ms=0.0,
        provider="gateway",
        model="none",
        error_type=error_type,
        error_message=message,
    )
