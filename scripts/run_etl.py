#!/usr/bin/env python3
"""
One-shot ETL trigger outside Dagster.
Usage: python scripts/run_etl.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from rich import print as rprint

log = structlog.get_logger()


def main():
    rprint("[bold blue]AdSignal ETL[/bold blue] — MongoDB → Iceberg")
    rprint("Checking Java version...")

    import subprocess
    result = subprocess.run(["java", "-version"], capture_output=True, text=True)
    if result.returncode != 0:
        rprint("[bold red]ERROR:[/bold red] Java not found. PySpark requires Java 17+.")
        rprint("Run: winget install Microsoft.OpenJDK.17")
        sys.exit(1)

    rprint("Starting PySpark ETL pipeline...")

    from adsignal.spark.etl import run_etl
    stats = run_etl()

    rprint("\n[bold green]✓ ETL Complete[/bold green]")
    rprint(f"  Raw rows written:    {stats['raw_rows']:,}")
    rprint(f"  Signal rows written: {stats['signal_rows']:,}")


if __name__ == "__main__":
    main()
