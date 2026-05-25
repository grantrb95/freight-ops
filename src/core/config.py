"""
Centralized configuration loading for the freight operations platform.

Reads ``config/config.yaml`` and builds typed domain objects from it. Currently
covers maintenance schedules, service history, and odometer readings; other
sections can be added as agents need them.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, Optional, Union

import yaml

from src.data.models.maintenance import (
    EquipmentCategory,
    MaintenanceRecord,
    MaintenanceSchedule,
    MaintenanceType,
    OdometerReading,
    ServiceInterval,
    VerificationStatus,
)

DEFAULT_CONFIG_PATH = "config/config.yaml"

# Fallbacks used when the maintenance section omits thresholds. These match the
# defaults on MaintenanceSchedule.
_DEFAULT_DUE_SOON_MILES = 500
_DEFAULT_DUE_SOON_DAYS = 14

# Seed service history is recorded from recollection until confirmed against
# paperwork, so it loads as provisional unless the entry says otherwise.
_DEFAULT_RECORD_VERIFICATION = VerificationStatus.PROVISIONAL


def load_config(path: Union[str, Path] = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load and parse the YAML configuration file into a dict."""
    text = Path(path).read_text()
    config = yaml.safe_load(text)
    if not isinstance(config, dict):
        raise ValueError(f"Config at {path} did not parse to a mapping")
    return config


def load_service_history(
    config: Optional[dict[str, Any]] = None,
    path: Union[str, Path] = DEFAULT_CONFIG_PATH,
) -> list[MaintenanceRecord]:
    """
    Build completed-service records from ``maintenance.service_history``.

    Each record's verification status defaults to ``provisional`` (seeded from
    recollection) unless the entry sets ``verification`` explicitly.

    Raises:
        ValueError: If an entry references an unknown maintenance type,
            equipment category, or verification status.
    """
    if config is None:
        config = load_config(path)

    maintenance = config.get("maintenance", {})
    items = maintenance.get("service_history", [])

    records: list[MaintenanceRecord] = []
    for item in items:
        unit = item["unit"]
        mtype = MaintenanceType(item["type"])
        service_date = item["date"]
        verification = VerificationStatus(
            item.get("verification", _DEFAULT_RECORD_VERIFICATION.value)
        )
        records.append(
            MaintenanceRecord(
                record_id=item.get("record_id", f"{unit}-{mtype.value}-{service_date}"),
                unit_id=unit,
                equipment=EquipmentCategory(unit),
                maintenance_type=mtype,
                service_date=service_date,
                odometer=item["odometer"],
                cost=Decimal(str(item.get("cost", "0"))),
                vendor=item.get("vendor"),
                description=item.get("description"),
                notes=item.get("notes"),
                verification_status=verification,
            )
        )
    return records


def load_odometers(
    config: Optional[dict[str, Any]] = None,
    path: Union[str, Path] = DEFAULT_CONFIG_PATH,
) -> dict[str, OdometerReading]:
    """Build current odometer readings (keyed by unit_id) from ``odometers``."""
    if config is None:
        config = load_config(path)

    odometers: dict[str, Any] = config.get("odometers", {})
    readings: dict[str, OdometerReading] = {}
    for unit_id, data in odometers.items():
        readings[unit_id] = OdometerReading(
            unit_id=unit_id,
            miles=data["miles"],
            last_verified_date=data.get("last_verified_date"),
            source=data.get("source"),
        )
    return readings


def _apply_service_history(
    schedules: list[MaintenanceSchedule], records: list[MaintenanceRecord]
) -> None:
    """Set each schedule's baseline from its most recent matching service record."""
    latest: dict[tuple[str, MaintenanceType], MaintenanceRecord] = {}
    for record in records:
        key = (record.unit_id, record.maintenance_type)
        if key not in latest or record.service_date > latest[key].service_date:
            latest[key] = record

    for schedule in schedules:
        matched = latest.get((schedule.unit_id, schedule.maintenance_type))
        if matched is not None:
            schedule.apply_service(matched)


def load_maintenance_schedules(
    config: Optional[dict[str, Any]] = None,
    path: Union[str, Path] = DEFAULT_CONFIG_PATH,
    apply_history: bool = True,
) -> list[MaintenanceSchedule]:
    """
    Build maintenance schedules from configuration.

    Args:
        config: An already-loaded config mapping. If omitted, it is read from
            ``path``.
        path: Path to the config file (used only when ``config`` is None).
        apply_history: When True, seed each schedule's baseline from the most
            recent matching record in ``maintenance.service_history``.

    Returns:
        One MaintenanceSchedule per item under ``maintenance.schedules``.

    Raises:
        ValueError: If a schedule item references an unknown maintenance type or
            equipment category, or omits both interval dimensions.
    """
    if config is None:
        config = load_config(path)

    maintenance = config.get("maintenance", {})
    due_soon_miles = maintenance.get("due_soon_miles", _DEFAULT_DUE_SOON_MILES)
    due_soon_days = maintenance.get("due_soon_days", _DEFAULT_DUE_SOON_DAYS)
    warranty_types = {MaintenanceType(t) for t in maintenance.get("warranty_critical", [])}
    schedules_by_category: dict[str, Any] = maintenance.get("schedules", {})

    schedules: list[MaintenanceSchedule] = []
    for category, items in schedules_by_category.items():
        equipment = EquipmentCategory(category)
        for item in items:
            mtype = MaintenanceType(item["type"])
            schedules.append(
                MaintenanceSchedule(
                    unit_id=category,
                    equipment=equipment,
                    maintenance_type=mtype,
                    interval=ServiceInterval(
                        miles=item.get("miles"),
                        months=item.get("months"),
                    ),
                    # Passed explicitly: without the pydantic mypy plugin, mypy
                    # does not recognize Field(None) defaults and treats these as
                    # required. A freshly loaded schedule has no service history.
                    last_service_date=None,
                    last_service_odometer=None,
                    last_service_verification=VerificationStatus.UNVERIFIED,
                    warranty_critical=mtype in warranty_types,
                    due_soon_miles=due_soon_miles,
                    due_soon_days=due_soon_days,
                )
            )

    if apply_history:
        _apply_service_history(schedules, load_service_history(config))
    return schedules
