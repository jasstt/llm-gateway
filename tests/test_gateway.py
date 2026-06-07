"""
test_gateway.py — Temel gateway testleri.
Çalıştır: python tests/test_gateway.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.rate_limiter import RateLimiter, RateLimitExceeded
from src.budget import BudgetManager, BudgetExceeded
from src.circuit_breaker import CircuitBreaker, CircuitBreakerOpen, CircuitState

PASS = "✅ PASS"
FAIL = "❌ FAIL"


def test_rate_limit_user():
    """20 istekten sonra 429 dönmeli."""
    limiter = RateLimiter(user_limit=20, ip_limit=100)
    errors = 0
    for i in range(25):
        try:
            limiter.check(user_id="test_user", ip="1.2.3.4")
        except RateLimitExceeded as e:
            errors += 1
            assert e.status_code == 429
    assert errors == 5, f"Beklenen 5 hata, gelen: {errors}"
    print(f"[test_rate_limit_user] {PASS} — 20 kabul, 5 × 429 reddedildi.")


def test_rate_limit_ip():
    """IP limiti (5) aşılınca 429 dönmeli."""
    limiter = RateLimiter(user_limit=100, ip_limit=5)
    errors = 0
    for i in range(8):
        try:
            limiter.check(user_id=f"user_{i}", ip="9.9.9.9")
        except RateLimitExceeded as e:
            errors += 1
            assert e.status_code == 429
    assert errors == 3, f"Beklenen 3 hata, gelen: {errors}"
    print(f"[test_rate_limit_ip] {PASS} — IP limiti aşımında 429 döndü.")


def test_budget_exceeded():
    """Bütçesi dolmuş ekip 402 ile reddedilmeli."""
    bm = BudgetManager()
    bm.reset("team_beta")

    # Bütçeyi manuel olarak aş
    import json
    path = "data/budgets.json"
    with open(path, "r") as f:
        data = json.load(f)
    data["team_beta"]["spent_usd"] = data["team_beta"]["budget_usd"] + 0.5
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    raised = False
    try:
        bm.check_and_reserve("team_beta")
    except BudgetExceeded as e:
        raised = True
        assert e.status_code == 402

    assert raised, "BudgetExceeded bekleniyor ama fırlatılmadı!"
    print(f"[test_budget_exceeded] {PASS} — Bütçe aşımında 402 döndü.")

    # Sıfırla
    bm.reset("team_beta")


def test_budget_deduction():
    """Başarılı istek sonrası bütçeden düşülmeli."""
    bm = BudgetManager()
    bm.reset("team_alpha")

    before = bm.get_status("team_alpha")["spent_usd"]
    bm.deduct("team_alpha", 0.00042)
    after = bm.get_status("team_alpha")["spent_usd"]

    diff = round(after - before, 8)
    assert abs(diff - 0.00042) < 1e-9, f"Beklenen 0.00042, fark: {diff}"
    print(f"[test_budget_deduction] {PASS} — $0.00042 bütçeden düşüldü.")

    bm.reset("team_alpha")


def test_circuit_breaker_opens():
    """3 üst üste hata sonrası circuit breaker açılmalı."""
    cb = CircuitBreaker("test_provider", failure_threshold=3, recovery_timeout=60)

    assert cb.state == CircuitState.CLOSED

    for _ in range(3):
        cb.record_failure()

    assert cb.state == CircuitState.OPEN, f"State: {cb.state}"

    raised = False
    try:
        cb.allow_request()
    except CircuitBreakerOpen as e:
        raised = True
        assert e.status_code == 503

    assert raised, "CircuitBreakerOpen bekleniyor ama fırlatılmadı!"
    print(f"[test_circuit_breaker_opens] {PASS} — 3 hata sonrası devre açıldı, 503 döndü.")


def test_circuit_breaker_half_open():
    """60sn sonra HALF_OPEN moda geçmeli; başarılıysa CLOSED dönmeli."""
    import time
    cb = CircuitBreaker("test_provider2", failure_threshold=3, recovery_timeout=1)

    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    time.sleep(1.1)  # Timeout geç

    # allow_request HALF_OPEN'a geçirmeli
    allowed = cb.allow_request()
    assert allowed
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    print(f"[test_circuit_breaker_half_open] {PASS} — Timeout sonrası HALF_OPEN → başarı → CLOSED.")


def test_circuit_breaker_success_resets():
    """Başarılı istek failure_count'u sıfırlamalı."""
    cb = CircuitBreaker("test_provider3", failure_threshold=3, recovery_timeout=60)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb._failure_count == 0
    print(f"[test_circuit_breaker_success_resets] {PASS} — Başarılı istek sayacı sıfırladı.")


def run_all():
    print("\n" + "=" * 60)
    print("  LLM GATEWAY — Unit Testler")
    print("=" * 60)

    tests = [
        test_rate_limit_user,
        test_rate_limit_ip,
        test_budget_exceeded,
        test_budget_deduction,
        test_circuit_breaker_opens,
        test_circuit_breaker_half_open,
        test_circuit_breaker_success_resets,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"[{test.__name__}] {FAIL} — AssertionError: {e}")
            failed += 1
        except Exception as e:
            print(f"[{test.__name__}] {FAIL} — Exception: {type(e).__name__}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"  Sonuç: {passed} PASS | {failed} FAIL | Toplam: {len(tests)}")
    print("=" * 60 + "\n")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
