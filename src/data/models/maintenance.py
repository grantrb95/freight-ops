"""
Maintenance data models - vehicle and equipment service tracking.

These models track preventive maintenance for the fleet (truck and trailer):
service intervals, completed service records, and computed due/overdue status.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from dateutil.relativedelta import relativedelta
from pydantic import BaseModel, Field, computed_field, model_validator


class EquipmentCategory(str, Enum):
    """Category of equipment a maintenance item applies to."""

    TRUCK = "truck"
    TRAILER = "trailer"


class MaintenanceType(str, Enum):
    """Type of maintenance or service performed."""

    # Truck (diesel) services
    OIL_CHANGE = "oil_change"
    TIRE_ROTATION = "tire_rotation"
    TIRE_REPLACEMENT = "tire_replacement"
    BRAKE_SERVICE = "brake_service"
    TRANSMISSION_SERVICE = "transmission_service"
    FUEL_FILTER = "fuel_filter"
    AIR_FILTER = "air_filter"
    COOLANT_FLUSH = "coolant_flush"
    DEF_SYSTEM = "def_system"
    # Trailer services
    WHEEL_BEARING = "wheel_bearing"
    GREASE_LUBE = "grease_lube"
    LIGHT_INSPECTION = "light_inspection"
    # Shared / regulatory
    DOT_INSPECTION = "dot_inspection"
    GENERAL_REPAIR = "general_repair"


class MaintenanceStatus(str, Enum):
    """Service status relative to its interval."""

    OK = "ok"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"


class VerificationStatus(str, Enum):
    """Confidence in a service record's accuracy."""

    VERIFIED = "verified"  # Confirmed against documentation (receipt, work order)
    PROVISIONAL = "provisional"  # Seeded from recollection, pending verification
    UNVERIFIED = "unverified"  # No record on file


class ServiceInterval(BaseModel):
    """
    Recurrence interval for a maintenance item.

    At least one of ``miles`` or ``months`` must be provided. When both are set,
    whichever comes first determines that the service is due.
    """

    miles: Optional[int] = Field(None, gt=0, description="Mileage between services")
    months: Optional[int] = Field(None, gt=0, description="Months between services")

    @model_validator(mode="after")
    def _require_interval(self) -> "ServiceInterval":
        """Ensure at least one dimension is specified."""
        if self.miles is None and self.months is None:
            raise ValueError("ServiceInterval requires at least one of 'miles' or 'months'")
        return self


class MaintenanceRecord(BaseModel):
    """A completed/logged service event for a unit of equipment."""

    record_id: str = Field(..., description="Unique maintenance record identifier")
    unit_id: str = Field(..., description="Equipment unit this record applies to")
    equipment: EquipmentCategory = Field(..., description="Equipment category")
    maintenance_type: MaintenanceType = Field(..., description="Type of service performed")

    service_date: datetime = Field(..., description="When the service was performed")
    odometer: int = Field(..., ge=0, description="Odometer (or hub miles) at service time")

    cost: Decimal = Field(Decimal("0"), ge=0, description="Total cost of the service (USD)")
    vendor: Optional[str] = Field(None, description="Shop or vendor that performed the service")
    description: Optional[str] = Field(None, description="Short description of work done")
    notes: Optional[str] = Field(None, description="Additional notes")
    verification_status: VerificationStatus = Field(
        VerificationStatus.UNVERIFIED,
        description="Whether this record has been verified against documentation",
    )

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v),
        }


class MaintenanceSchedule(BaseModel):
    """
    A recurring maintenance item for a unit of equipment.

    Tracks the last completed service (date and/or odometer) and computes when
    the next service is due. Status is evaluated against a current odometer
    reading and date via :meth:`evaluate`.
    """

    unit_id: str = Field(..., description="Equipment unit this schedule applies to")
    equipment: EquipmentCategory = Field(..., description="Equipment category")
    maintenance_type: MaintenanceType = Field(..., description="Type of service")
    interval: ServiceInterval = Field(..., description="How often the service recurs")

    last_service_date: Optional[datetime] = Field(
        None, description="Date of the most recent service"
    )
    last_service_odometer: Optional[int] = Field(
        None, ge=0, description="Odometer at the most recent service"
    )

    due_soon_miles: int = Field(
        500, ge=0, description="Flag as due-soon when within this many miles"
    )
    due_soon_days: int = Field(
        14, ge=0, description="Flag as due-soon when within this many days"
    )

    last_service_verification: VerificationStatus = Field(
        VerificationStatus.UNVERIFIED,
        description="Verification status of the baseline (last) service",
    )
    warranty_critical: bool = Field(
        False,
        description="Service must be dealer-performed to preserve factory warranty",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def next_due_odometer(self) -> Optional[int]:
        """Odometer at which the next service is due (mileage interval only)."""
        if self.interval.miles is None or self.last_service_odometer is None:
            return None
        return self.last_service_odometer + self.interval.miles

    @computed_field  # type: ignore[prop-decorator]
    @property
    def next_due_date(self) -> Optional[datetime]:
        """Date at which the next service is due (time interval only)."""
        if self.interval.months is None or self.last_service_date is None:
            return None
        return self.last_service_date + relativedelta(months=self.interval.months)

    def miles_remaining(self, current_odometer: int) -> Optional[int]:
        """Miles until the next mileage-based service (negative if overdue)."""
        due = self.next_due_odometer
        if due is None:
            return None
        return due - current_odometer

    def days_remaining(self, as_of: datetime) -> Optional[int]:
        """Days until the next time-based service (negative if overdue)."""
        due = self.next_due_date
        if due is None:
            return None
        return (due - as_of).days

    def evaluate(self, current_odometer: int, as_of: datetime) -> MaintenanceStatus:
        """
        Determine service status from the most urgent of its dimensions.

        A schedule with no recorded baseline service is treated as ``DUE_SOON``
        so an initial service can be logged.
        """
        statuses: list[MaintenanceStatus] = []

        miles_rem = self.miles_remaining(current_odometer)
        if miles_rem is not None:
            if miles_rem < 0:
                statuses.append(MaintenanceStatus.OVERDUE)
            elif miles_rem <= self.due_soon_miles:
                statuses.append(MaintenanceStatus.DUE_SOON)
            else:
                statuses.append(MaintenanceStatus.OK)

        days_rem = self.days_remaining(as_of)
        if days_rem is not None:
            if days_rem < 0:
                statuses.append(MaintenanceStatus.OVERDUE)
            elif days_rem <= self.due_soon_days:
                statuses.append(MaintenanceStatus.DUE_SOON)
            else:
                statuses.append(MaintenanceStatus.OK)

        if not statuses:
            # No baseline service recorded yet for either dimension.
            return MaintenanceStatus.DUE_SOON
        if MaintenanceStatus.OVERDUE in statuses:
            return MaintenanceStatus.OVERDUE
        if MaintenanceStatus.DUE_SOON in statuses:
            return MaintenanceStatus.DUE_SOON
        return MaintenanceStatus.OK

    def apply_service(self, record: MaintenanceRecord) -> None:
        """Update the schedule's baseline from a completed service record."""
        self.last_service_date = record.service_date
        self.last_service_odometer = record.odometer
        self.last_service_verification = record.verification_status

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v),
        }


class MaintenanceAlert(BaseModel):
    """A flagged maintenance item produced when evaluating a fleet."""

    unit_id: str
    equipment: EquipmentCategory
    maintenance_type: MaintenanceType
    status: MaintenanceStatus
    miles_remaining: Optional[int] = None
    days_remaining: Optional[int] = None
    next_due_odometer: Optional[int] = None
    next_due_date: Optional[datetime] = None
    message: str
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    warranty_critical: bool = False

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class OdometerReading(BaseModel):
    """A current odometer reading with provenance, for staleness checks."""

    unit_id: str = Field(..., description="Equipment unit this reading applies to")
    miles: int = Field(..., ge=0, description="Current odometer / hub miles")
    last_verified_date: Optional[datetime] = Field(
        None, description="When this reading was last verified against its source"
    )
    source: Optional[str] = Field(None, description="Where the reading came from (e.g. ELD)")

    def is_stale(self, as_of: datetime, max_age_days: int = 7) -> bool:
        """True when the reading has not been verified within ``max_age_days``."""
        if self.last_verified_date is None:
            return True
        return (as_of - self.last_verified_date).days > max_age_days

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}
