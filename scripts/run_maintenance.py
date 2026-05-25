#!/usr/bin/env python3
"""
Fleet maintenance report — the first runtime entrypoint for MaintenanceAgent.

Reads ``config/config.yaml`` (schedules, service history, odometers via the
config loaders), evaluates every schedule against the current odometer and date,
and prints a scannable report.

Usage:
    uv run python scripts/run_maintenance.py                 # text, as of today
    uv run python scripts/run_maintenance.py --format json
    uv run python scripts/run_maintenance.py --as-of 2026-05-25
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.agents.maintenance import MaintenanceAgent
from src.core.config import load_config, load_odometers
from src.data.models.maintenance import (
    MaintenanceAlert,
    MaintenanceStatus,
    OdometerReading,
    VerificationStatus,
)

# Default config lives at <repo>/config/config.yaml, regardless of cwd.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG = _REPO_ROOT / "config" / "config.yaml"
_STALE_AFTER_DAYS = 7

_STATUS_HEADINGS = [
    (MaintenanceStatus.OVERDUE, "OVERDUE"),
    (MaintenanceStatus.DUE_SOON, "DUE SOON"),
    (MaintenanceStatus.OK, "OK"),
]


@dataclass
class MaintenanceReport:
    """Everything needed to render a maintenance report."""

    as_of: datetime
    alerts: list[MaintenanceAlert]
    odometers: dict[str, OdometerReading]
    stale_units: list[str]
    max_age_days: int


def build_report(
    config: dict[str, Any],
    as_of: datetime,
    max_age_days: int = _STALE_AFTER_DAYS,
) -> MaintenanceReport:
    """Evaluate the fleet and assemble a report from a loaded config mapping."""
    agent = MaintenanceAgent.from_config(config=config)
    odometers = load_odometers(config)
    current_odometers = {unit_id: reading.miles for unit_id, reading in odometers.items()}

    alerts = agent.evaluate_fleet(current_odometers, as_of)
    stale_units = [
        unit_id
        for unit_id, reading in odometers.items()
        if reading.is_stale(as_of, max_age_days)
    ]
    return MaintenanceReport(
        as_of=as_of,
        alerts=alerts,
        odometers=odometers,
        stale_units=stale_units,
        max_age_days=max_age_days,
    )


def _service_name(alert: MaintenanceAlert) -> str:
    return alert.maintenance_type.value.replace("_", " ")


def _detail(alert: MaintenanceAlert) -> str:
    """Human-readable urgency detail for a single alert."""
    miles, days = alert.miles_remaining, alert.days_remaining

    if alert.status is MaintenanceStatus.OVERDUE:
        parts = []
        if miles is not None and miles < 0:
            parts.append(f"{abs(miles):,} mi past due")
        if days is not None and days < 0:
            parts.append(f"{abs(days):,} days past due")
        return ", ".join(parts) or "overdue"

    if alert.status is MaintenanceStatus.DUE_SOON:
        if miles is None and days is None:
            return "no service on record"
        parts = []
        if miles is not None and miles >= 0:
            parts.append(f"{miles:,} mi left")
        if days is not None and days >= 0:
            parts.append(f"{days:,} days left")
        return ", ".join(parts) or "due soon"

    parts = []
    if miles is not None:
        parts.append(f"{miles:,} mi left")
    if days is not None:
        parts.append(f"{days:,} days left")
    return ", ".join(parts) or "ok"


def _markers(alert: MaintenanceAlert) -> str:
    tags = []
    if alert.verification_status is VerificationStatus.PROVISIONAL:
        tags.append("[?]")
    if alert.warranty_critical:
        tags.append("[warranty: dealer]")
    return ("  " + " ".join(tags)) if tags else ""


def render_text(report: MaintenanceReport) -> str:
    """Render a scannable plain-text report."""
    lines: list[str] = []
    bar = "=" * 70
    lines.append(bar)
    lines.append(f" Fleet Maintenance Report - as of {report.as_of.date().isoformat()}")
    lines.append(bar)

    # Odometers + staleness.
    lines.append(" Odometers:")
    if report.odometers:
        for unit_id, reading in sorted(report.odometers.items()):
            src = reading.source or "unknown source"
            verified = (
                reading.last_verified_date.date().isoformat()
                if reading.last_verified_date
                else "never"
            )
            stale = "   [STALE - re-verify]" if unit_id in report.stale_units else ""
            lines.append(f"   {unit_id:<8} {reading.miles:>9,} mi   ({src}, verified {verified}){stale}")
    else:
        lines.append("   (none configured)")
    if report.stale_units:
        lines.append(
            f"   ! odometer not verified within {report.max_age_days} days: "
            f"{', '.join(sorted(report.stale_units))}"
        )

    # Status groups.
    counts = {status: 0 for status, _ in _STATUS_HEADINGS}
    for alert in report.alerts:
        counts[alert.status] += 1

    for status, heading in _STATUS_HEADINGS:
        group = [a for a in report.alerts if a.status is status]
        lines.append("")
        lines.append(f" {heading} ({counts[status]})")
        if not group:
            lines.append("   (none)")
            continue
        for alert in group:
            lines.append(
                f"   {alert.unit_id:<8} {_service_name(alert):<20} "
                f"{_detail(alert):<22}{_markers(alert)}"
            )

    # Warranty-critical items needing service, called out separately.
    warranty_due = [
        a
        for a in report.alerts
        if a.warranty_critical and a.status is not MaintenanceStatus.OK
    ]
    if warranty_due:
        lines.append("")
        lines.append("-" * 70)
        lines.append(" WARRANTY-CRITICAL - dealer service required to preserve factory warranty:")
        for alert in warranty_due:
            lines.append(
                f"   {alert.unit_id:<8} {_service_name(alert):<20} {alert.status.value.upper()}"
            )

    # Legend (only when relevant).
    if any(a.verification_status is VerificationStatus.PROVISIONAL for a in report.alerts):
        lines.append("")
        lines.append(" [?] = provisional service record, pending verification")

    return "\n".join(line.rstrip() for line in lines)


def render_json(report: MaintenanceReport) -> str:
    """Render the report as JSON."""
    payload = {
        "as_of": report.as_of.isoformat(),
        "odometers": {
            unit_id: reading.model_dump(mode="json")
            for unit_id, reading in report.odometers.items()
        },
        "stale_units": report.stale_units,
        "summary": {
            "overdue": sum(1 for a in report.alerts if a.status is MaintenanceStatus.OVERDUE),
            "due_soon": sum(1 for a in report.alerts if a.status is MaintenanceStatus.DUE_SOON),
            "ok": sum(1 for a in report.alerts if a.status is MaintenanceStatus.OK),
            "warranty_critical_due": sum(
                1
                for a in report.alerts
                if a.warranty_critical and a.status is not MaintenanceStatus.OK
            ),
        },
        "alerts": [alert.model_dump(mode="json") for alert in report.alerts],
    }
    return json.dumps(payload, indent=2)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate fleet maintenance from config.")
    parser.add_argument(
        "--config",
        type=Path,
        default=_DEFAULT_CONFIG,
        help="Path to config.yaml (default: <repo>/config/config.yaml)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--as-of",
        type=str,
        default=None,
        help="Evaluation date (ISO, e.g. 2026-05-25). Defaults to now.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else datetime.now()

    config = load_config(args.config)
    report = build_report(config, as_of)

    output = render_json(report) if args.format == "json" else render_text(report)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
