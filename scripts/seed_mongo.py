#!/usr/bin/env python3
"""
Seed MongoDB with synthetic ad creative data for all configured brands.
Usage: python scripts/seed_mongo.py [--brands nike adidas] [--weeks 16] [--ads-per-week 50]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from adsignal.config import settings
from adsignal.ingest.mongo_writer import upsert_creatives
from adsignal.ingest.synthetic import generate_brand_batch

log = structlog.get_logger()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brands", nargs="+", default=settings.brands)
    parser.add_argument("--weeks", type=int, default=16)
    parser.add_argument("--ads-per-week", type=int, default=50)
    args = parser.parse_args()

    total_upserted = 0
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn()) as progress:
        task = progress.add_task("Seeding MongoDB...", total=len(args.brands))
        for brand in args.brands:
            progress.update(task, description=f"Generating {brand}...")
            docs = generate_brand_batch(brand, n_weeks=args.weeks, ads_per_week=args.ads_per_week)
            result = upsert_creatives(docs)
            total_upserted += result["upserted"]
            log.info("brand_seeded", brand=brand, upserted=result["upserted"], docs_generated=len(docs))
            progress.advance(task)

    print(f"\n✓ Seeding complete. Total upserted: {total_upserted:,}")


if __name__ == "__main__":
    main()
