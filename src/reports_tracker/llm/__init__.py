from ..config import Settings
from .base import Extractor


def get_extractor(settings: Settings, backend: str | None = None) -> Extractor:
    backend = backend or settings.llm
    if backend == "gemini":
        from .gemini import GeminiExtractor
        return GeminiExtractor(settings.gemini_api_key, settings.gemini_model, settings.max_chars)
    if backend == "ollama":
        from .ollama import OllamaExtractor
        return OllamaExtractor(settings.ollama_url, settings.ollama_model, settings.max_chars)
    if backend == "rules":
        from .rules import RulesExtractor
        return RulesExtractor()
    raise ValueError(f"Unknown LLM backend {backend!r}; use gemini, ollama or rules")
