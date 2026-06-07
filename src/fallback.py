"""
fallback.py — Provider sırası ve otomatik geçiş.
config.py'deki PROVIDER_ORDER listesine göre provider'ları sırayla dener.
Birincil provider başarısız olursa sıradakine geçer ve bunu loglar.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import PROVIDER_ORDER
from src.providers.base import BaseProvider, ProviderResponse
from src.circuit_breaker import get_circuit_breaker, CircuitBreakerOpen


def _load_providers() -> dict[str, BaseProvider]:
    """Kayıtlı provider'ları lazy-load eder."""
    providers: dict[str, BaseProvider] = {}
    for name in PROVIDER_ORDER:
        if name == "gemini":
            from src.providers.gemini import GeminiProvider
            try:
                providers["gemini"] = GeminiProvider()
            except Exception as e:
                print(f"[FALLBACK] '{name}' provider yüklenemedi: {e}")
    return providers


class FallbackRouter:
    """
    PROVIDER_ORDER sırasına göre provider'ları dener.
    Circuit breaker açıksa o provider'ı atlar.
    Tüm provider'lar başarısız olursa FallbackExhausted fırlatır.
    """

    def __init__(self):
        self._providers = _load_providers()
        self._order = PROVIDER_ORDER

    def complete(self, prompt: str, user_id: str = "unknown") -> ProviderResponse:
        last_error: str = "Hiçbir provider bulunamadı."

        for provider_name in self._order:
            if provider_name not in self._providers:
                print(f"[FALLBACK] '{provider_name}' provider listede değil, atlanıyor.")
                continue

            cb = get_circuit_breaker(provider_name)

            # Circuit breaker kontrolü
            try:
                cb.allow_request()
            except CircuitBreakerOpen as e:
                print(f"[FALLBACK] '{provider_name}' devre dışı ({e}). Sıradakine geçiliyor...")
                last_error = str(e)
                continue

            # Provider'a istek at
            provider = self._providers[provider_name]
            response = provider.complete(prompt, user_id)

            if response.success:
                cb.record_success()
                if provider_name != self._order[0]:
                    print(
                        f"[FALLBACK] Birincil provider başarısız olduğu için "
                        f"'{provider_name}' kullanıldı."
                    )
                return response
            else:
                # Başarısız → circuit breaker'a bildir
                print(
                    f"[FALLBACK] '{provider_name}' hata verdi: "
                    f"{response.error_type} — {response.error_message}"
                )
                cb.record_failure()
                last_error = f"{response.error_type}: {response.error_message}"

        # Tüm provider'lar başarısız
        raise FallbackExhausted(
            f"Tüm provider'lar başarısız oldu. Son hata: {last_error}"
        )


class FallbackExhausted(Exception):
    """Tüm provider'lar denendikten sonra fırlatılır."""
    def __init__(self, message: str):
        super().__init__(message)
        self.status_code = 502  # Bad Gateway
