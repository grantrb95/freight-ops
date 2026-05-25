"""
Pydantic data models for freight operations.

Core models:
- Load: Freight shipment details
- Route: Pickup/delivery locations and routing
- Rate: Pricing and rate information
- Driver: Driver and equipment information
- Expense: Cost tracking
- Settlement: Driver pay calculations
- Maintenance: Vehicle/equipment service tracking
"""

from .load import Load, LoadStatus, LoadType, Location
from .maintenance import (
    EquipmentCategory,
    MaintenanceAlert,
    MaintenanceRecord,
    MaintenanceSchedule,
    MaintenanceStatus,
    MaintenanceType,
    ServiceInterval,
)

__all__ = [
    "Load",
    "LoadStatus",
    "LoadType",
    "Location",
    "EquipmentCategory",
    "MaintenanceAlert",
    "MaintenanceRecord",
    "MaintenanceSchedule",
    "MaintenanceStatus",
    "MaintenanceType",
    "ServiceInterval",
]
