"""
Centralized configuration loading for the freight operations platform.

Reads ``config/config.yaml`` and builds typed domain objects from it. Currently
covers the maintenance schedules; other sections can be added as agents need
them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

import yaml

from src.data.models.maintenance import (
    EquipmentCategory,
    MaintenanceSchedule,
    MaintenanceType,
    ServiceInterval,
)

DEFAULT_CONFIG_PATH = "config/config.yaml"

# Fallbacks used when the maintenance section omits thresholds. These match the
# defaults on MaintenanceSchedule.
_DEFAULT_DUE_SOON_MILES = 500
_DEFAULT_DUE_SOON_DAYS = 14


def load_config(path: Union[str, Path] = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load and parse the YAML configuration file into a dict."""
    text = Path(path).read_text()
    config = yaml.safe_load(text)
    if not isinstance(config, dict):
        raise ValueError(f"Config at {path} did not parse to a mapping")
    return config


def load_maintenance_schedules(
    config: Optional[dict[str, Any]] = None,
    path: Union[str, Path] = DEFAULT_CONFIG_PATH,
) -> list[MaintenanceSchedule]:
    """
    Build maintenance schedules from configuration.

    Args:
        config: An already-loaded config mapping. If omitted, it is read from
            ``path``.
        path: Path to the config file (used only when ``config`` is None).

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
    schedules_by_category: dict[str, Any] = maintenance.get("schedules", {})

    schedules: list[MaintenanceSchedule] = []
    for category, items in schedules_by_category.items():
        equipment = EquipmentCategory(category)
        for item in items:
            schedules.append(
                MaintenanceSchedule(
                    unit_id=category,
                    equipment=equipment,
                    maintenance_type=MaintenanceType(item["type"]),
                    interval=ServiceInterval(
                        miles=item.get("miles"),
                        months=item.get("months"),
                    ),
                    # Passed explicitly: without the pydantic mypy plugin, mypy
                    # does not recognize Field(None) defaults and treats these as
                    # required. A freshly loaded schedule has no service history.
                    last_service_date=None,
                    last_service_odometer=None,
                    due_soon_miles=due_soon_miles,
                    due_soon_days=due_soon_days,
                )
            )
    return schedules
