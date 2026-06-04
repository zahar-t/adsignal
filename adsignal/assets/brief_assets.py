from dagster import AssetIn, MetadataValue, Output, asset

from adsignal.llm.narrative import generate_brief


@asset(
    group_name="intelligence",
    ins={"brand_signal_summaries": AssetIn()},
    description="Generate LLM competitive intelligence briefs for all brands",
)
def brand_briefs(context, brand_signal_summaries: dict) -> Output[dict]:
    """Generate analyst briefs via LLM for each brand."""
    briefs = {}
    for brand, summary in brand_signal_summaries.items():
        context.log.info(f"Generating brief for {brand}")
        brief = generate_brief(brand, summary)
        briefs[brand] = brief
        context.log.info(f"Brief generated: {brief[:80]}...")

    return Output(
        value=briefs,
        metadata={"briefs_generated": MetadataValue.int(len(briefs))},
    )
