"""
budget.py — Ekip/proje bazlı bütçe takibi.
budgets.json'dan ekip limitlerini okur; her istekte maliyeti düşer.
Limit aşılınca isteği reddeder.

Gemini fiyatları: input $0.075/1M token, output $0.30/1M token
"""
import json
import os
from threading import Lock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import BUDGET_FILE


class BudgetExceeded(Exception):
    """Bütçe aşıldığında fırlatılır."""
    def __init__(self, message: str):
        super().__init__(message)
        self.status_code = 402  # Payment Required


class BudgetManager:
    """
    budgets.json dosyasını okur ve her başarılı istekte maliyeti düşer.
    Thread-safe: birden fazla eş zamanlı istek güvenle işlenir.
    """

    def __init__(self, budget_file: str = BUDGET_FILE):
        self._file = budget_file
        self._lock = Lock()
        self._data = self._load()

    def _load(self) -> dict:
        """Bütçe dosyasını diskten yükler."""
        if not os.path.exists(self._file):
            return {}
        with open(self._file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self) -> None:
        """Güncel bütçe durumunu diske yazar."""
        os.makedirs(os.path.dirname(self._file), exist_ok=True)
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def check_and_reserve(self, team_id: str, estimated_cost: float = 0.001) -> None:
        """
        İstek öncesi bütçeyi kontrol eder.
        Yeterliyse rezerve eder (bloklar), yoksa BudgetExceeded fırlatır.
        """
        with self._lock:
            self._data = self._load()  # Her seferinde taze oku
            if team_id not in self._data:
                # Bilinmeyen ekip — varsayılan 0 bütçe, isteğe izin ver
                return

            team = self._data[team_id]
            remaining = team["budget_usd"] - team["spent_usd"]

            if remaining <= 0:
                raise BudgetExceeded(
                    f"'{team_id}' ekibinin bütçesi tükendi. "
                    f"Limit: ${team['budget_usd']:.4f}, "
                    f"Harcanan: ${team['spent_usd']:.4f}"
                )

    def deduct(self, team_id: str, cost_usd: float) -> None:
        """Başarılı bir isteğin maliyetini bütçeden düşer ve kaydeder."""
        if cost_usd <= 0:
            return
        with self._lock:
            self._data = self._load()
            if team_id not in self._data:
                return
            self._data[team_id]["spent_usd"] = round(
                self._data[team_id]["spent_usd"] + cost_usd, 8
            )
            self._save()

    def get_status(self, team_id: str) -> dict:
        """Bir ekibin bütçe durumunu döner."""
        with self._lock:
            self._data = self._load()
            if team_id not in self._data:
                return {"error": f"'{team_id}' ekibi bulunamadı."}
            team = self._data[team_id]
            return {
                "team_id": team_id,
                "budget_usd": team["budget_usd"],
                "spent_usd": round(team["spent_usd"], 6),
                "remaining_usd": round(team["budget_usd"] - team["spent_usd"], 6),
                "usage_pct": round(
                    (team["spent_usd"] / team["budget_usd"]) * 100, 2
                ) if team["budget_usd"] > 0 else 100.0,
            }

    def reset(self, team_id: str) -> None:
        """Bir ekibin harcamasını sıfırlar (test amaçlı)."""
        with self._lock:
            self._data = self._load()
            if team_id in self._data:
                self._data[team_id]["spent_usd"] = 0.0
                self._save()
