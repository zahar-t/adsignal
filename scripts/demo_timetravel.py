#!/usr/bin/env python3
"""
Iceberg snapshot comparison demo — shows time-travel capabilities.

Demonstrates:
1. List all snapshots for brand_weekly_signals
2. Read data at a specific snapshot (point-in-time)
3. Compare two snapshots week-over-week for a brand

Usage: python scripts/demo_timetravel.py [--brand nike]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich import print as rprint
from rich.table import Table

from adsignal.catalog import get_catalog_reader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", default="nike")
    args = parser.parse_args()

    catalog = get_catalog_reader()

    try:
        table = catalog.load_table("ad_intelligence.brand_weekly_signals")
    except Exception as e:
        rprint(f"[red]Could not load table: {e}[/red]")
        rprint("Run 'make bootstrap && make seed && make etl' first.")
        sys.exit(1)

    # List snapshots
    snapshots = list(table.snapshots())
    if not snapshots:
        rprint("[yellow]No snapshots found. Run 'make etl' first.[/yellow]")
        sys.exit(0)

    rprint("\n[bold]Iceberg Snapshots for brand_weekly_signals[/bold]")
    rprint(f"Total snapshots: {len(snapshots)}\n")

    snap_table = Table(show_header=True)
    snap_table.add_column("Snapshot ID", style="cyan")
    snap_table.add_column("Timestamp (ms)")
    snap_table.add_column("Operation")
    snap_table.add_column("Added Records")

    for snap in sorted(snapshots, key=lambda s: s.snapshot_id):
        summary = snap.summary or {}
        # rich needs strings — `operation` is an Operation enum and `added-records`
        # is an int, so coerce both before adding the row.
        snap_table.add_row(
            str(snap.snapshot_id),
            str(snap.timestamp_ms),
            str(summary.get("operation", "unknown")),
            str(summary.get("added-records", "—")),
        )
    rprint(snap_table)

    # Time-travel: read at latest snapshot
    rprint(f"\n[bold]Brand data for '{args.brand}' at latest snapshot:[/bold]")
    try:
        df = table.scan(
            row_filter=f"brand = '{args.brand}'"
        ).to_pandas()

        if df.empty:
            rprint(f"[yellow]No data found for brand: {args.brand}[/yellow]")
        else:
            weekly = (
                df.groupby("week_key")["spend_midpoint"]
                .sum()
                .reset_index()
                .sort_values("week_key")
                .tail(8)
            )
            rprint(weekly.to_string(index=False))

    except Exception as e:
        rprint(f"[red]Scan error: {e}[/red]")

    # If multiple snapshots, compare latest vs previous
    if len(snapshots) >= 2:
        sorted_snaps = sorted(snapshots, key=lambda s: s.snapshot_id)
        prev_snap = sorted_snaps[-2]
        curr_snap = sorted_snaps[-1]

        rprint(f"\n[bold]Week-over-week delta (snapshot {prev_snap.snapshot_id} → {curr_snap.snapshot_id}):[/bold]")
        try:
            df_prev = table.scan(
                snapshot_id=prev_snap.snapshot_id,
                row_filter=f"brand = '{args.brand}'"
            ).to_pandas()

            df_curr = table.scan(
                snapshot_id=curr_snap.snapshot_id,
                row_filter=f"brand = '{args.brand}'"
            ).to_pandas()

            spend_prev = df_prev["spend_midpoint"].sum() if not df_prev.empty else 0
            spend_curr = df_curr["spend_midpoint"].sum() if not df_curr.empty else 0
            delta = spend_curr - spend_prev
            pct = (delta / (spend_prev + 1e-9)) * 100

            rprint(f"  Previous total spend: ${spend_prev:,.0f}")
            rprint(f"  Current total spend:  ${spend_curr:,.0f}")
            rprint(f"  Delta: {delta:+,.0f} ({pct:+.1f}%)")
        except Exception as e:
            rprint(f"[yellow]Could not compare snapshots: {e}[/yellow]")


if __name__ == "__main__":
    main()
