"""
Maintenance Agent - monitors fleet service schedules.

Evaluates each maintenance schedule against current odometer readings and the
current date, flags items that are due-soon or overdue, and logs its reasoning.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

from src.agents.base import BaseAgent
from src.core.config import DEFAULT_CONFIG_PATH, load_config, load_maintenance_schedules
from src.data.models.maintenance import (
    MaintenanceAlert,
    MaintenanceSchedule,
    MaintenanceStatus,
)

# Status ordering used to sort alerts most-urgent first.
_URGENCY = {
    MaintenanceStatus.OVERDUE: 0,
    MaintenanceStatus.DUE_SOON: 1,
    MaintenanceStatus.OK: 2,
}


def _build_message(schedule: MaintenanceSchedule, status: MaintenanceStatus,
                   miles_remaining: Optional[int], days_remaining: Optional[int]) -> str:
    """Compose a human-readable alert message."""
    service = schedule.maintenance_type.value.replace("_", " ")
    unit = f"{schedule.unit_id} ({schedule.equipment.value})"

    if status is MaintenanceStatus.OVERDUE:
        parts = []
        if miles_remaining is not None and miles_remaining < 0:
            parts.append(f"{abs(miles_remaining)} mi past due")
        if days_remaining is not None and days_remaining < 0:
            parts.append(f"{abs(days_remaining)} days past due")
        detail = ", ".join(parts) if parts else "service baseline missing"
        return f"OVERDUE: {service} on {unit} ({detail})"

    if status is MaintenanceStatus.DUE_SOON:
        parts = []
        if miles_remaining is not None and miles_remaining >= 0:
            parts.append(f"{miles_remaining} mi remaining")
        if days_remaining is not None and days_remaining >= 0:
            parts.append(f"{days_remaining} days remaining")
        detail = ", ".join(parts) if parts else "no baseline service recorded"
        return f"Due soon: {service} on {unit} ({detail})"

    return f"OK: {service} on {unit}"


class MaintenanceAgent(BaseAgent):
    """Agent that tracks preventive maintenance across the fleet."""

    def __init__(
        self,
        schedules: Optional[Iterable[MaintenanceSchedule]] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__("maintenance", config)
        self.schedules: list[MaintenanceSchedule] = list(schedules or [])

    @classmethod
    def from_config(
        cls,
        path: Union[str, Path] = DEFAULT_CONFIG_PATH,
        config: Optional[dict[str, Any]] = None,
    ) -> "MaintenanceAgent":
        """Build an agent with schedules loaded from configuration."""
        loaded = config if config is not None else load_config(path)
        schedules = load_maintenance_schedules(loaded)
        return cls(schedules=schedules, config=loaded)

    def evaluate_fleet(
        self,
        current_odometers: dict[str, int],
        as_of: Optional[datetime] = None,
    ) -> list[MaintenanceAlert]:
        """
        Evaluate every schedule and return alerts sorted most-urgent first.

        Args:
            current_odometers: Current odometer reading keyed by unit_id.
            as_of: Evaluation date (defaults to now).

        Returns:
            Alerts for every schedule, ordered overdue -> due-soon -> ok.
        """
        as_of = as_of or datetime.now()
        alerts: list[MaintenanceAlert] = []

        for schedule in self.schedules:
            odometer = current_odometers.get(schedule.unit_id, schedule.last_service_odometer or 0)
            status = schedule.evaluate(odometer, as_of)
            miles_remaining = schedule.miles_remaining(odometer)
            days_remaining = schedule.days_remaining(as_of)

            alert = MaintenanceAlert(
                unit_id=schedule.unit_id,
                equipment=schedule.equipment,
                maintenance_type=schedule.maintenance_type,
                status=status,
                miles_remaining=miles_remaining,
                days_remaining=days_remaining,
                next_due_odometer=schedule.next_due_odometer,
                next_due_date=schedule.next_due_date,
                message=_build_message(schedule, status, miles_remaining, days_remaining),
                verification_status=schedule.last_service_verification,
                warranty_critical=schedule.warranty_critical,
            )
            alerts.append(alert)

            if status is not MaintenanceStatus.OK:
                self.log_decision(
                    alert.message,
                    data_considered={
                        "unit_id": schedule.unit_id,
                        "maintenance_type": schedule.maintenance_type.value,
                        "current_odometer": odometer,
                        "as_of": as_of.isoformat(),
                        "miles_remaining": miles_remaining,
                        "days_remaining": days_remaining,
                    },
                    rules_applied=[
                        f"due_soon_miles<={schedule.due_soon_miles}",
                        f"due_soon_days<={schedule.due_soon_days}",
                    ],
                    rationale=f"Flagged {schedule.maintenance_type.value} as {status.value}.",
                )

        alerts.sort(key=lambda a: (_URGENCY[a.status], a.unit_id, a.maintenance_type.value))
        return alerts

    def due_items(
        self,
        current_odometers: dict[str, int],
        as_of: Optional[datetime] = None,
    ) -> list[MaintenanceAlert]:
        """Return only the alerts that need attention (due-soon or overdue)."""
        return [
            alert
            for alert in self.evaluate_fleet(current_odometers, as_of)
            if alert.status is not MaintenanceStatus.OK
        ]

    def run(
        self,
        current_odometers: dict[str, int],
        as_of: Optional[datetime] = None,
    ) -> list[MaintenanceAlert]:
        """Execute the agent: evaluate the fleet and return all alerts."""
        return self.evaluate_fleet(current_odometers, as_of)
