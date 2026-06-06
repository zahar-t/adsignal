"""
Model-agnostic LLM client.
Controlled by LLM_PROVIDER env var: ollama | lmstudio | anthropic | openai

Ollama:    uses openai-compatible endpoint at OLLAMA_BASE_URL
LM Studio: uses openai-compatible endpoint at LMSTUDIO_BASE_URL
Anthropic: uses anthropic SDK directly
OpenAI:    uses openai SDK

All paths return a plain string (the narrative text).
"""
from typing import Any, cast

import structlog

from adsignal.config import settings

log = structlog.get_logger()


def complete(prompt: str, system: str | None = None) -> str:
    """
    Send a prompt to the configured LLM provider and return the text response.

    Args:
        prompt: user message
        system: optional system prompt

    Returns:
        str: model response text
    """
    provider = settings.llm_provider.lower()

    if provider == "ollama":
        return _complete_ollama(prompt, system)
    elif provider == "lmstudio":
        return _complete_lmstudio(prompt, system)
    elif provider == "anthropic":
        return _complete_anthropic(prompt, system)
    elif provider == "openai":
        return _complete_openai(prompt, system)
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: {provider}. Must be ollama | lmstudio | anthropic | openai"
        )


def _complete_ollama(prompt: str, system: str | None) -> str:
    """Use Ollama via OpenAI-compatible endpoint."""
    from openai import OpenAI

    client = OpenAI(
        base_url=f"{settings.ollama_base_url}/v1",
        api_key="ollama",  # required by openai SDK, ignored by Ollama
    )
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=cast(Any, messages),
            max_tokens=512,
            temperature=0.3,  # lower temp for analytical prose
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        log.error("ollama_completion_failed", error=str(e))
        return f"[LLM Error: {e}]"


def _complete_lmstudio(prompt: str, system: str | None) -> str:
    """Use LM Studio via its OpenAI-compatible local server."""
    from openai import OpenAI

    client = OpenAI(
        base_url=settings.lmstudio_base_url,
        api_key="lm-studio",  # required by openai SDK, ignored by LM Studio
    )
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=cast(Any, messages),
            max_tokens=512,
            temperature=0.3,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        log.error("lmstudio_completion_failed", error=str(e))
        return f"[LLM Error: {e}]"


def _complete_anthropic(prompt: str, system: str | None) -> str:
    """Use Anthropic Claude API directly."""
    import anthropic

    if not settings.anthropic_api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not set. Use LLM_PROVIDER=ollama or lmstudio for local inference."
        )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    kwargs: dict[str, Any] = {
        "model": settings.llm_model or "claude-sonnet-4-20250514",
        "max_tokens": 512,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    try:
        message = client.messages.create(**kwargs)
        return message.content[0].text
    except Exception as e:
        log.error("anthropic_completion_failed", error=str(e))
        return f"[LLM Error: {e}]"


def _complete_openai(prompt: str, system: str | None) -> str:
    """Use OpenAI API."""
    from openai import OpenAI

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY not set.")

    client = OpenAI(api_key=settings.openai_api_key)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model=settings.llm_model or "gpt-4o-mini",
            messages=cast(Any, messages),
            max_tokens=512,
            temperature=0.3,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        log.error("openai_completion_failed", error=str(e))
        return f"[LLM Error: {e}]"
