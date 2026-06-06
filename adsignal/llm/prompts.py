"""
Prompt templates for the narrative engine.
Kept separate from logic for easy iteration.
"""

SYSTEM_PROMPT = """You are a senior media analyst at a competitive intelligence firm.
You analyse ad spend signals from public sources and write concise, data-driven briefs
for marketing strategy teams. Your writing is direct, specific, and cites the data.
Never use filler phrases like 'it appears' or 'it seems'. Write in active voice.
Maximum 3 sentences per brief unless otherwise specified."""


def build_brief_prompt(brand: str, signal_summary: dict) -> str:
    """
    Build the competitive intelligence brief prompt.
    Structures quantitative signal data as readable context for the LLM.
    """
    channel_mix = signal_summary.get("channel_mix_pct", {})
    channel_mix_str = ", ".join(
        f"{ch}: {pct}%" for ch, pct in sorted(channel_mix.items(), key=lambda x: -x[1])
    )

    anomaly_weeks = signal_summary.get("anomaly_weeks", [])
    anomaly_str = ", ".join(anomaly_weeks[-3:]) if anomaly_weeks else "none detected"

    # Per-channel trend summary
    channel_trends = []
    for ch, forecast in signal_summary.get("channel_forecasts", {}).items():
        direction = forecast.get("trend_direction", "flat")
        pct = forecast.get("trend_pct_change", 0)
        channel_trends.append(f"{ch}: {direction} ({pct:+.1f}%)")
    trends_str = " | ".join(channel_trends) if channel_trends else "insufficient data"

    top_themes = signal_summary.get("top_themes", [])
    themes_str = ", ".join(top_themes) if top_themes else "unavailable"

    n_weeks = signal_summary.get("weeks_analysed", 0)
    dominant_trend = signal_summary.get("dominant_trend", "flat")

    # Defense in depth: themes originate from external ad metadata. Even though
    # ingest already sanitizes, strip any invisible-Unicode smuggling here too so
    # nothing hidden reaches the model in the assembled prompt (ECC integration).
    from adsignal.security import sanitize_external_text

    themes_str = sanitize_external_text(themes_str)

    prompt = f"""Analyse the following competitive ad intelligence signals for {brand.upper()} and write a 3-sentence analyst brief.

SIGNAL DATA ({n_weeks} weeks of observations):
- Overall spend trend: {dominant_trend}
- Channel mix (recent 4 weeks): {channel_mix_str}
- Per-channel trends: {trends_str}
- Anomalous weeks detected: {anomaly_str}
- Dominant creative themes: {themes_str}

BRIEF REQUIREMENTS:
1. Sentence 1: Describe the overall spend posture and trend direction with specific channel data.
2. Sentence 2: Call out the most significant channel shift or anomaly, citing specific weeks or percentages.
3. Sentence 3: Infer a strategic implication for a media buyer competing against this brand.

Write only the 3-sentence brief. No preamble. No bullet points."""

    return prompt
