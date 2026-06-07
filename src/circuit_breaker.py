"""
circuit_breaker.py — Provider hata yönetimi.
3 üst üste hata → 60 sn devre dışı → yarı açık modda 1 deneme.
"""
import time
from enum import Enum
from threading import Lock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import CIRCUIT_BREAKER_FAILURE_THRESHOLD, CIRCUIT_BREAKER_RECOVERY_TIMEOUT


class CircuitState(Enum):
    CLOSED = "closed"        # Normal çalışma
    OPEN = "open"            # Hatalı, istekler engellendi
    HALF_OPEN = "half_open"  # Deneme aşamasında


class CircuitBreakerOpen(Exception):
    """Circuit breaker açık olduğunda fırlatılır."""
    def __init__(self, provider: str, retry_after: int):
        super().__init__(
            f"Provider '{provider}' devre dışı (circuit breaker açık). "
            f"{retry_after} saniye sonra tekrar deneyin."
        )
        self.status_code = 503
        self.provider = provider
        self.retry_after = retry_after


class CircuitBreaker:
    """
    Her provider için ayrı bir circuit breaker instance'ı tutulur.
    States: CLOSED → (3 hata) → OPEN → (60sn) → HALF_OPEN → (başarı) → CLOSED
    """

    def __init__(
        self,
        provider_name: str,
        failure_threshold: int = CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        recovery_timeout: int = CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
    ):
        self._provider = provider_name
        self._threshold = failure_threshold
        self._timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float = 0.0
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    def allow_request(self) -> bool:
        """İsteğe izin verilip verilmeyeceğini döner."""
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                elapsed = time.time() - self._opened_at
                if elapsed >= self._timeout:
                    # Yarı açık moda geç — tek deneme hakkı
                    print(
                        f"[CIRCUIT] '{self._provider}' yarı açık moda geçti "
                        f"({elapsed:.0f}sn sonra). Deneme yapılıyor..."
                    )
                    self._state = CircuitState.HALF_OPEN
                    return True
                retry_after = int(self._timeout - elapsed) + 1
                raise CircuitBreakerOpen(self._provider, retry_after)

            # HALF_OPEN → tek deneme hakkı zaten verildi
            return True

    def record_success(self) -> None:
        """Başarılı istek kaydeder — devre kapatılır."""
        with self._lock:
            if self._state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
                print(f"[CIRCUIT] '{self._provider}' başarılı yanıt — devre kapatıldı.")
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Başarısız istek kaydeder. Eşik aşılırsa devreyi açar."""
        with self._lock:
            self._failure_count += 1

            if self._state == CircuitState.HALF_OPEN:
                # Yarı açık modda hata → tekrar OPEN
                print(
                    f"[CIRCUIT] '{self._provider}' yarı açık modda hata verdi — "
                    f"devre tekrar açıldı."
                )
                self._state = CircuitState.OPEN
                self._opened_at = time.time()
                return

            if self._failure_count >= self._threshold:
                print(
                    f"[CIRCUIT] '{self._provider}' {self._failure_count} üst üste hata — "
                    f"devre {self._timeout}sn açıldı!"
                )
                self._state = CircuitState.OPEN
                self._opened_at = time.time()

    def get_status(self) -> dict:
        """Mevcut devre durumunu döner."""
        with self._lock:
            info = {
                "provider": self._provider,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "threshold": self._threshold,
            }
            if self._state == CircuitState.OPEN:
                elapsed = time.time() - self._opened_at
                info["time_until_half_open_secs"] = max(
                    0, int(self._timeout - elapsed)
                )
            return info


# Global circuit breaker registry (provider adı → instance)
_registry: dict[str, CircuitBreaker] = {}
_registry_lock = Lock()


def get_circuit_breaker(provider_name: str) -> CircuitBreaker:
    """Provider adına göre singleton circuit breaker döner."""
    with _registry_lock:
        if provider_name not in _registry:
            _registry[provider_name] = CircuitBreaker(provider_name)
        return _registry[provider_name]
