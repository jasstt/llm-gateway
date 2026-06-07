"""
gemini.py — Google Gemini API wrapper. Token sayısını ve maliyeti hesaplar.
"""
import os
import time
from dotenv import load_dotenv
from google import genai

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from config import GEMINI_MODEL, GEMINI_INPUT_COST_PER_1M, GEMINI_OUTPUT_COST_PER_1M
from src.providers.base import BaseProvider, ProviderResponse

load_dotenv()


class GeminiProvider(BaseProvider):
    """Google Gemini API provider."""

    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY ortam değişkeni ayarlanmamış.")
        self._client = genai.Client(api_key=api_key)
        self._model = GEMINI_MODEL

    @property
    def name(self) -> str:
        return "gemini"

    def is_available(self) -> bool:
        return True  # Circuit breaker bu kontrolü yönetir

    def complete(self, prompt: str, user_id: str = "unknown") -> ProviderResponse:
        start = time.time()
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
            )
            latency_ms = (time.time() - start) * 1000

            # Token sayılarını çek
            usage = response.usage_metadata
            input_tokens = getattr(usage, "prompt_token_count", 0) or 0
            output_tokens = getattr(usage, "candidates_token_count", 0) or 0

            # Maliyet hesapla
            cost = (
                (input_tokens / 1_000_000) * GEMINI_INPUT_COST_PER_1M +
                (output_tokens / 1_000_000) * GEMINI_OUTPUT_COST_PER_1M
            )

            return ProviderResponse(
                success=True,
                text=response.text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=round(cost, 8),
                latency_ms=round(latency_ms, 2),
                provider=self.name,
                model=self._model,
            )

        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            error_type = type(e).__name__
            return ProviderResponse(
                success=False,
                text="",
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                latency_ms=round(latency_ms, 2),
                provider=self.name,
                model=self._model,
                error_type=error_type,
                error_message=str(e),
            )
