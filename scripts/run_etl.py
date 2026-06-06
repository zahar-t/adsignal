#!/usr/bin/env python3
"""
One-shot ETL trigger outside Dagster.

Usage:
    python scripts/run_etl.py                 # auto: Spark if Java 17+, else pandas
    python scripts/run_etl.py --engine spark  # force PySpark (needs Java 17+)
    python scripts/run_etl.py --engine pandas # force Spark-free PyIceberg path

The pandas engine produces an identical brand_weekly_signals table without a JVM,
so the pipeline runs on machines / CI runners that lack Java 17. See
adsignal/etl_pandas.py.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from rich import print as rprint

from adsignal.spark.java import MIN_JAVA_MAJOR, find_java_home, java_major

log = structlog.get_logger()

MIN_JAVA_FOR_SPARK = MIN_JAVA_MAJOR


def spark_java_available() -> bool:
    """Whether a Java 17+ JDK is discoverable anywhere on this machine."""
    return find_java_home(MIN_JAVA_FOR_SPARK) is not None


def main():
    parser = argparse.ArgumentParser(description="Run the AdSignal ETL.")
    parser.add_argument(
        "--engine",
        choices=["auto", "spark", "pandas"],
        default="auto",
        help="ETL engine (default: auto — Spark when Java 17+ is present, else pandas).",
    )
    args = parser.parse_args()

    rprint("[bold blue]AdSignal ETL[/bold blue] — MongoDB → Iceberg")

    engine = args.engine
    if engine == "auto":
        java_home = find_java_home(MIN_JAVA_FOR_SPARK)
        if java_home is None:
            rprint(
                f"No Java {MIN_JAVA_FOR_SPARK}+ JDK found — using the Spark-free "
                "[bold]pandas[/bold] engine."
            )
            engine = "pandas"
        else:
            major = java_major(f"{java_home}/bin/java")
            rprint(f"Java {major} found at {java_home} — using the [bold]PySpark[/bold] engine.")
            engine = "spark"

    if engine == "spark":
        if not spark_java_available():
            rprint(
                f"[bold red]ERROR:[/bold red] --engine spark requires Java {MIN_JAVA_FOR_SPARK}+, "
                "none found. Install it (macOS: `brew install openjdk@17`) or use --engine pandas."
            )
            sys.exit(1)
        rprint("Starting PySpark ETL pipeline...")
        from adsignal.spark.etl import run_etl

        stats = run_etl()
    else:
        rprint("Starting pandas ETL pipeline (PyIceberg, no JVM)...")
        from adsignal.etl_pandas import run_pandas_etl

        stats = run_pandas_etl()

    rprint("\n[bold green]✓ ETL Complete[/bold green]")
    rprint(f"  Raw rows read:       {stats['raw_rows']:,}")
    rprint(f"  Signal rows written: {stats['signal_rows']:,}")


if __name__ == "__main__":
    main()
