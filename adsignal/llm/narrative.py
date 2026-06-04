"""
High-level narrative generation API.
Combines signal_builder + LLM provider.
"""
import structlog

from adsignal.llm.prompts import SYSTEM_PROMPT, build_brief_prompt
from adsignal.llm.provider import complete

log = structlog.get_logger()


def generate_brief(brand: str, signal_summary: dict) -> str:
    """
    Generate a competitive intelligence brief for a brand.

    Args:
        brand: brand slug
        signal_summary: dict from signal_builder.build_signal_summary()

    Returns:
        str: 3-sentence analyst brief
    """
    if signal_summary.get("error"):
        return f"Insufficient data for {brand}: {signal_summary['error']}"

    prompt = build_brief_prompt(brand, signal_summary)

    from adsignal.config import settings
    log.info("generating_brief", brand=brand, provider=settings.llm_provider)

    brief = complete(prompt=prompt, system=SYSTEM_PROMPT)
    return brief.strip()
