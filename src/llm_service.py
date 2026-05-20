"""하위 호환 — MessageClassifier 사용 권장."""

from src.llm_router import MessageClassifier

GeminiClassifier = MessageClassifier

__all__ = ["MessageClassifier", "GeminiClassifier"]
