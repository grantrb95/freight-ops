"""
Load data model - represents a freight shipment.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class LoadStatus(str, Enum):
    """Load status enumeration."""

    AVAILABLE = "available"
    BOOKED = "booked"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class LoadType(str, Enum):
    """Type of load."""

    FULL = "full"
    PARTIAL = "partial"
    EXPEDITED = "expedited"
    TEAM = "team"
    HAZMAT = "hazmat"


class Location(BaseModel):
    """Geographic location."""

    city: str
    state: str
    zip_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    def __str__(self) -> str:
        """String representation."""
        return f"{self.city}, {self.state}"


class Load(BaseModel):
    """
    Represents a freight load/shipment.

    This is the core data model for load operations.
    """

    # Identification
    load_id: str = Field(..., description="Unique load identifier")
    broker_name: Optional[str] = Field(None, description="Broker or shipper name")
    broker_mc: Optional[str] = Field(None, description="Broker MC number")
    reference_number: Optional[str] = Field(None, description="Customer reference number")

    # Status
    status: LoadStatus = Field(LoadStatus.AVAILABLE, description="Current load status")
    posted_date: datetime = Field(
        default_factory=datetime.now, description="When load was posted"
    )

    # Locations
    origin: Location = Field(..., description="Pickup location")
    destination: Location = Field(..., description="Delivery location")

    # Timing
    pickup_date: datetime = Field(..., description="Scheduled pickup date/time")
    delivery_date: datetime = Field(..., description="Scheduled delivery date/time")
    pickup_window_start: Optional[datetime] = None
    pickup_window_end: Optional[datetime] = None

    # Load details
    commodity: str = Field(..., description="Type of freight (e.g., 'Auto Parts')")
    weight: int = Field(..., gt=0, description="Weight in pounds")
    length: Optional[int] = Field(None, description="Length in feet")
    load_type: LoadType = Field(LoadType.FULL, description="Type of load")

    # Financial
    rate: Decimal = Field(..., gt=0, description="Total rate offered (USD)")
    fuel_surcharge: Decimal = Field(Decimal("0"), description="Fuel surcharge (USD)")
    additional_charges: Decimal = Field(Decimal("0"), description="Accessorial charges (USD)")

    # Distance
    loaded_miles: int = Field(..., gt=0, description="Distance from pickup to delivery")
    deadhead_miles: int = Field(0, ge=0, description="Empty miles to pickup")

    # Special requirements
    is_hazmat: bool = Field(False, description="Requires hazmat certification")
    is_team_required: bool = Field(False, description="Requires team drivers")
    is_expedited: bool = Field(False, description="Time-sensitive delivery")
    requires_tarp: bool = Field(False, description="Requires tarping")

    # Equipment
    equipment_type: str = Field("Hotshot", description="Equipment type needed")
    trailer_type: Optional[str] = Field(None, description="Specific trailer type")

    # Contact
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None

    # Notes
    notes: Optional[str] = Field(None, description="Additional load details")

    @computed_field
    @property
    def total_miles(self) -> int:
        """Total miles including deadhead."""
        return self.loaded_miles + self.deadhead_miles

    @computed_field
    @property
    def deadhead_percentage(self) -> float:
        """Deadhead as percentage of total miles."""
        if self.total_miles == 0:
            return 0.0
        return (self.deadhead_miles / self.total_miles) * 100

    @computed_field
    @property
    def gross_revenue(self) -> Decimal:
        """Total revenue including all charges."""
        return self.rate + self.fuel_surcharge + self.additional_charges

    @computed_field
    @property
    def rate_per_mile(self) -> Decimal:
        """Rate per loaded mile."""
        if self.loaded_miles == 0:
            return Decimal("0")
        return self.gross_revenue / Decimal(self.loaded_miles)

    @computed_field
    @property
    def all_miles_rate(self) -> Decimal:
        """Rate per mile including deadhead."""
        if self.total_miles == 0:
            return Decimal("0")
        return self.gross_revenue / Decimal(self.total_miles)

    @computed_field
    @property
    def trip_duration_hours(self) -> float:
        """Estimated trip duration in hours."""
        delta = self.delivery_date - self.pickup_date
        return delta.total_seconds() / 3600

    def is_profitable(self, min_rpm: Decimal, max_deadhead_pct: float) -> bool:
        """
        Check if load meets profitability criteria.

        Args:
            min_rpm: Minimum acceptable rate per mile
            max_deadhead_pct: Maximum acceptable deadhead percentage

        Returns:
            True if load meets both criteria
        """
        return (
            self.rate_per_mile >= min_rpm and self.deadhead_percentage <= max_deadhead_pct
        )

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v),
        }
