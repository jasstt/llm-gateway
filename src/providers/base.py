"""
base.py — Tüm LLM provider'ları için soyut temel sınıf.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderResponse:
    """Bir provider'dan gelen standart yanıt."""
    success: bool
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    provider: str
    model: str
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class BaseProvider(ABC):
    """Tüm provider wrapper'larının uygulaması gereken arayüz."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider adı (örn. 'gemini')."""
        ...

    @abstractmethod
    def complete(self, prompt: str, user_id: str = "unknown") -> ProviderResponse:
        """
        Verilen prompt'u tamamlar.

        Args:
            prompt: Kullanıcı girdisi
            user_id: İzleme/loglama için kullanıcı kimliği

        Returns:
            ProviderResponse nesnesi
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Provider'ın şu an erişilebilir olup olmadığını döner."""
        ...
