"""Centralized provider configuration for LLM models.

Supports switching between Gemini, OpenAI, and NVIDIA models at runtime
via a provider dropdown in the frontend.
"""

import contextvars
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Context variable holding the current provider for the active request.
# Set by the agent at the start of each request so tools can read it.
current_provider: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_provider", default="gemini"
)

PROVIDERS: dict[str, dict[str, Any]] = {
    "gemini": {
        "primary_model": "gemini-2.5-flash",
        "secondary_model": "gemini-2.5-flash",
        "embedding_model": "gemini-embedding-001",
        "model_provider": "openai",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GEMINI_API_KEY",
    },
    "openai": {
        "primary_model": "gpt-5.2",
        "secondary_model": "gpt-5-nano-2025-08-07",
        "embedding_model": "text-embedding-3-small",
        "model_provider": "openai",  # for LangChain init_chat_model
        "api_key_env": "OPENAI_API_KEY",
    },
    "nvidia": {
        "primary_model": "nvidia/llama-3.3-nemotron-super-49b-v1",
        "secondary_model": "nvidia/llama-3.1-nemotron-nano-8b-v1",
        "embedding_model": "nvidia/nv-embedqa-e5-v5",
        "model_provider": "nvidia",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key_env": "NVIDIA_API_KEY",
    },
}


def get_provider_config(provider: str | None = None) -> dict[str, Any]:
    """Return config for the given provider, falling back to Gemini."""
    if provider is None:
        provider = current_provider.get("gemini")
    return PROVIDERS.get(provider, PROVIDERS["gemini"])


def get_secondary_client(provider: str | None = None) -> AsyncOpenAI:
    """Return an OpenAI-compatible async client for the given provider.

    If *provider* is None, reads from the current_provider context variable.
    """
    cfg = get_provider_config(provider)
    base_url = cfg.get("base_url")
    api_key_env = cfg.get("api_key_env")
    if base_url or api_key_env:
        return AsyncOpenAI(base_url=base_url, api_key=os.getenv(api_key_env))
    return AsyncOpenAI()  # uses OPENAI_API_KEY from env


def get_secondary_model(provider: str | None = None) -> str:
    """Return the secondary model name for the given provider."""
    return get_provider_config(provider)["secondary_model"]


def get_embedding_model(provider: str | None = None) -> str:
    """Return the embedding model name for the given provider."""
    return get_provider_config(provider)["embedding_model"]
