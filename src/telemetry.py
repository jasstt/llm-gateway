"""
telemetry.py — Her istek için OpenTelemetry formatında log yazar.
logs/requests.jsonl dosyasına timestamp, user_id, provider, model,
input_token, output_token, latency_ms, cost_usd, success, error_type yazılır.
"""
import json
import os
from datetime import datetime, timezone
from threading import Lock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import LOG_FILE
from src.providers.base import ProviderResponse


class Telemetry:
    """JSONL formatında istek loglarını yönetir."""

    def __init__(self, log_file: str = LOG_FILE):
        self._file = log_file
        self._lock = Lock()
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

    def log(
        self,
        user_id: str,
        team_id: str,
        prompt: str,
        response: ProviderResponse,
        extra: dict = None,
    ) -> dict:
        """
        Bir istek için log kaydı oluşturur ve JSONL dosyasına yazar.

        Returns:
            Yazılan log kaydı (dict)
        """
        record = {
            # OpenTelemetry uyumlu alanlar
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": _generate_trace_id(),

            # İstek kimlik bilgileri
            "user_id": user_id,
            "team_id": team_id,

            # Provider bilgileri
            "provider": response.provider,
            "model": response.model,

            # Token ve maliyet metrikleri
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.input_tokens + response.output_tokens,
            "cost_usd": response.cost_usd,

            # Performans
            "latency_ms": response.latency_ms,

            # Durum
            "success": response.success,
            "error_type": response.error_type,
            "error_message": response.error_message,

            # İsteğin özeti (tam prompt değil, ilk 100 karakter)
            "prompt_preview": prompt[:100] if prompt else "",
        }

        if extra:
            record.update(extra)

        with self._lock:
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return record

    def get_stats(self, limit: int = 100) -> dict:
        """Son N log kaydından istatistik çıkarır."""
        records = self._read_last(limit)
        if not records:
            return {"total_requests": 0}

        total = len(records)
        successful = sum(1 for r in records if r.get("success"))
        total_cost = sum(r.get("cost_usd", 0) for r in records)
        avg_latency = sum(r.get("latency_ms", 0) for r in records) / total

        return {
            "total_requests": total,
            "successful_requests": successful,
            "failed_requests": total - successful,
            "success_rate_pct": round(successful / total * 100, 1),
            "total_cost_usd": round(total_cost, 6),
            "avg_latency_ms": round(avg_latency, 1),
        }

    def _read_last(self, n: int) -> list[dict]:
        """Son N satırı okur."""
        if not os.path.exists(self._file):
            return []
        with open(self._file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        records = []
        for line in lines[-n:]:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return records


def _generate_trace_id() -> str:
    """Basit bir trace ID üretir (UUID benzeri)."""
    import uuid
    return str(uuid.uuid4()).replace("-", "")
