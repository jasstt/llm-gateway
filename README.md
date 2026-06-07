# LLM Gateway 🚀

A production-ready **LLM Gateway** that acts as a smart proxy between your application and LLM providers (currently Gemini). Every request passes through a full middleware pipeline: rate limiting → budget control → circuit breaker → provider fallback → telemetry logging.

---

## ✨ What It Does

| Layer | What It Handles |
|-------|----------------|
| **Rate Limiter** | 20 req/min per user, 100 req/min per IP (sliding window) |
| **Budget Manager** | Per-team token cost tracking, blocks when limit exceeded |
| **Circuit Breaker** | CLOSED → OPEN (3 failures) → HALF_OPEN (after 60s) → CLOSED |
| **Fallback Router** | Tries providers in priority order; skips broken ones |
| **Telemetry** | OpenTelemetry-compatible JSONL log for every request |

---

## 📁 Project Structure

```
llm-gateway/
├── src/
│   ├── gateway.py          # Main proxy — all requests flow through here
│   ├── rate_limiter.py     # Sliding-window, user & IP based rate limiting
│   ├── budget.py           # Per-team budget tracking (persisted to JSON)
│   ├── circuit_breaker.py  # Provider failure management (CLOSED/OPEN/HALF_OPEN)
│   ├── fallback.py         # Provider priority order + automatic failover
│   ├── telemetry.py        # Per-request log: latency, tokens, cost, errors
│   └── providers/
│       ├── base.py         # Abstract BaseProvider interface
│       └── gemini.py       # Google Gemini API wrapper with token & cost calc
├── data/
│   └── budgets.json        # Team budget limits (editable)
├── logs/
│   └── requests.jsonl      # Auto-generated per-request telemetry (gitignored)
├── tests/
│   └── test_gateway.py     # 7 unit tests — all pass without a live API call
├── main.py                 # CLI runner: 3 end-to-end demo scenarios
├── config.py               # All thresholds, model names, cost constants
└── requirements.txt
```

---

## 🚀 Getting Started

### 1. Clone & Install

```bash
git clone https://github.com/jasstt/llm-gateway.git
cd llm-gateway
pip install -r requirements.txt
```

### 2. Configure API Key

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=YOUR_KEY_HERE
```

Get a free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

### 3. (Optional) Adjust Team Budgets

Edit `data/budgets.json` to set per-team USD spending limits:

```json
{
  "team_alpha": { "budget_usd": 5.00, "spent_usd": 0.0 },
  "team_beta":  { "budget_usd": 0.001, "spent_usd": 0.0 }
}
```

### 4. Run the Demo Scenarios

```bash
python main.py
```

This runs 3 live scenarios:
1. **Normal request** — successful Gemini response with cost & latency logged
2. **Rate limit test** — 25 rapid requests from the same user; requests 21–25 get `429`
3. **Budget overflow test** — `team_beta` ($0.001 limit) is exhausted; second request gets `402`

### 5. Run Unit Tests (no API key needed)

```bash
python tests/test_gateway.py
```

---

## 📊 Test Results

| Test | Result |
|------|--------|
| Unit Tests | 7/7 PASS ✅ |
| Rate Limiting | 20 accepted, 5 rejected with `429` ✅ |
| Budget Control | $0.001 exceeded → `402 Payment Required` ✅ |
| Telemetry | Every request logged to `logs/requests.jsonl` ✅ |
| Latency | Avg. 4066ms (Gemini free tier) |

---

## ⚙️ Configuration (`config.py`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `PROVIDER_ORDER` | `["gemini"]` | Fallback priority list |
| `RATE_LIMIT_USER_PER_MINUTE` | `20` | Max requests per user per minute |
| `RATE_LIMIT_IP_PER_MINUTE` | `100` | Max requests per IP per minute |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `3` | Failures before opening circuit |
| `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | `60` | Seconds before HALF_OPEN retry |
| `GEMINI_INPUT_COST_PER_1M` | `$0.075` | Gemini input token cost |
| `GEMINI_OUTPUT_COST_PER_1M` | `$0.30` | Gemini output token cost |

---

## 📝 Telemetry Log Format

Every request appends a JSON line to `logs/requests.jsonl`:

```json
{
  "timestamp": "2026-06-07T13:38:02.123Z",
  "trace_id": "a1b2c3d4e5f6...",
  "user_id": "user_normal",
  "team_id": "team_alpha",
  "provider": "gemini",
  "model": "gemini-flash-latest",
  "input_tokens": 15,
  "output_tokens": 387,
  "total_tokens": 402,
  "cost_usd": 0.000117,
  "latency_ms": 5806.0,
  "success": true,
  "error_type": null,
  "error_message": null,
  "prompt_preview": "Yapay zekanın 3 temel uygulama alanını listele."
}
```

---

## 🛠 Technologies Used

* **[Google GenAI SDK](https://github.com/google/genai-python)** — Gemini API integration
* **[Pydantic](https://docs.pydantic.dev/)** — Data validation
* **[OpenTelemetry](https://opentelemetry.io/)** — Observability standards
* **[python-dotenv](https://pypi.org/project/python-dotenv/)** — Environment variable management

---

## 🔭 Roadmap

- [ ] Add OpenAI provider
- [ ] Add Anthropic provider  
- [ ] REST API layer (FastAPI)
- [ ] Dashboard UI for telemetry visualization
- [ ] Redis-backed distributed rate limiting
