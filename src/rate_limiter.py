"""
rate_limiter.py — Kullanıcı ve IP bazlı rate limiting.
Kullanıcı başına dakikada 20, IP başına dakikada 100 istek limiti.
Aşılırsa GatewayError(status=429) döner.
"""
import time
from collections import defaultdict, deque
from threading import Lock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import RATE_LIMIT_USER_PER_MINUTE, RATE_LIMIT_IP_PER_MINUTE


class RateLimitExceeded(Exception):
    """Rate limit aşıldığında fırlatılır."""
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.status_code = 429
        self.retry_after = retry_after


class RateLimiter:
    """
    Sliding window (kayan pencere) algoritmasıyla rate limiting.
    Thread-safe: birden fazla eş zamanlı istek güvenle işlenir.
    """

    def __init__(
        self,
        user_limit: int = RATE_LIMIT_USER_PER_MINUTE,
        ip_limit: int = RATE_LIMIT_IP_PER_MINUTE,
        window_seconds: int = 60,
    ):
        self._user_limit = user_limit
        self._ip_limit = ip_limit
        self._window = window_seconds

        # user_id → istek zaman damgaları (deque)
        self._user_windows: dict[str, deque] = defaultdict(deque)
        # ip → istek zaman damgaları (deque)
        self._ip_windows: dict[str, deque] = defaultdict(deque)

        self._lock = Lock()

    def _prune(self, dq: deque, now: float) -> None:
        """Pencere dışında kalan eski zaman damgalarını temizle."""
        cutoff = now - self._window
        while dq and dq[0] < cutoff:
            dq.popleft()

    def check(self, user_id: str, ip: str = "127.0.0.1") -> None:
        """
        İsteğin rate limit dahilinde olup olmadığını kontrol eder.
        Limit aşılırsa RateLimitExceeded fırlatır.
        Aksi hâlde isteği kaydeder.
        """
        now = time.time()
        with self._lock:
            # --- Kullanıcı bazlı kontrol ---
            udq = self._user_windows[user_id]
            self._prune(udq, now)
            if len(udq) >= self._user_limit:
                oldest = udq[0]
                retry_after = int(self._window - (now - oldest)) + 1
                raise RateLimitExceeded(
                    f"Kullanıcı '{user_id}' için rate limit aşıldı "
                    f"({self._user_limit} istek/dk). "
                    f"{retry_after} saniye sonra tekrar deneyin.",
                    retry_after=retry_after,
                )

            # --- IP bazlı kontrol ---
            idq = self._ip_windows[ip]
            self._prune(idq, now)
            if len(idq) >= self._ip_limit:
                oldest = idq[0]
                retry_after = int(self._window - (now - oldest)) + 1
                raise RateLimitExceeded(
                    f"IP '{ip}' için rate limit aşıldı "
                    f"({self._ip_limit} istek/dk). "
                    f"{retry_after} saniye sonra tekrar deneyin.",
                    retry_after=retry_after,
                )

            # Her iki kontrol geçti → kaydet
            udq.append(now)
            idq.append(now)

    def get_stats(self, user_id: str, ip: str = "127.0.0.1") -> dict:
        """Mevcut kullanım istatistiklerini döner."""
        now = time.time()
        with self._lock:
            udq = self._user_windows[user_id]
            self._prune(udq, now)
            idq = self._ip_windows[ip]
            self._prune(idq, now)
            return {
                "user_requests_last_minute": len(udq),
                "user_limit": self._user_limit,
                "ip_requests_last_minute": len(idq),
                "ip_limit": self._ip_limit,
            }
