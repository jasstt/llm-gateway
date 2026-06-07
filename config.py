"""
config.py — Provider sırası, rate limit değerleri, circuit breaker eşikleri.
"""

# Provider çalışma sırası (öncelik sırasına göre)
PROVIDER_ORDER = ["gemini"]

# Rate limiting
RATE_LIMIT_USER_PER_MINUTE = 20        # Kullanıcı başına dakikada max istek
RATE_LIMIT_IP_PER_MINUTE = 100         # IP başına dakikada max istek

# Circuit breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 3  # Kaç üst üste hata sonra açılır
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60  # Saniye cinsinden kapalı kalma süresi

# Gemini fiyatlandırması (USD / 1M token)
GEMINI_INPUT_COST_PER_1M = 0.075
GEMINI_OUTPUT_COST_PER_1M = 0.30

# Gemini modeli
GEMINI_MODEL = "gemini-flash-latest"

# Log dosyası
LOG_FILE = "logs/requests.jsonl"

# Bütçe dosyası
BUDGET_FILE = "data/budgets.json"
