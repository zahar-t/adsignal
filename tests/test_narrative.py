from unittest.mock import patch

from adsignal.llm.prompts import SYSTEM_PROMPT, build_brief_prompt
from adsignal.models.signal_builder import build_signal_summary


def test_build_brief_prompt_contains_brand(sample_signals_df):
    summary = build_signal_summary(sample_signals_df, "nike")
    prompt = build_brief_prompt("nike", summary)
    assert "NIKE" in prompt
    assert "BRIEF REQUIREMENTS" in prompt


def test_build_brief_prompt_contains_signal_data(sample_signals_df):
    summary = build_signal_summary(sample_signals_df, "nike")
    prompt = build_brief_prompt("nike", summary)
    assert "Channel mix" in prompt
    assert "SIGNAL DATA" in prompt


def test_generate_brief_calls_llm(sample_signals_df):
    summary = build_signal_summary(sample_signals_df, "nike")
    with patch("adsignal.llm.narrative.complete") as mock_complete:
        mock_complete.return_value = "Nike has been increasing video spend. Test brief."
        from adsignal.llm.narrative import generate_brief
        brief = generate_brief("nike", summary)
        assert len(brief) > 0
        mock_complete.assert_called_once()


def test_generate_brief_error_summary():
    from adsignal.llm.narrative import generate_brief
    brief = generate_brief("unknown", {"error": "no_data"})
    assert "Insufficient data" in brief


def test_system_prompt_contains_analyst_role():
    assert "media analyst" in SYSTEM_PROMPT.lower() or "analyst" in SYSTEM_PROMPT.lower()
