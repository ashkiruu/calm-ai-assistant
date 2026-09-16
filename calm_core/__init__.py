"""Deterministic, context-aware core for the CALM assistant."""

from .mission_contract import MissionContractError, MissionRegistry
from .llm import LLMProvider, LLMResult, LLMUnavailable, OllamaClient
from .openrouter import OpenRouterClient
from .rag_chat import RAGChatService
from .router import CALMAssistant, ContextValidationError
from .speech import EdgeSpeechSynthesizer, SpeechUnavailable
from .unity_crosswalk import CrosswalkValidationError, UnityScenarioCrosswalk

__all__ = [
    "CALMAssistant",
    "ContextValidationError",
    "CrosswalkValidationError",
    "EdgeSpeechSynthesizer",
    "LLMProvider",
    "LLMResult",
    "LLMUnavailable",
    "MissionContractError",
    "MissionRegistry",
    "OllamaClient",
    "OpenRouterClient",
    "RAGChatService",
    "SpeechUnavailable",
    "UnityScenarioCrosswalk",
]
