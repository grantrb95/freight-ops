"""
Compliance Agent - IFTA tracking, HOS monitoring, and DOT compliance.

This agent:
- Tracks fuel purchases and miles by jurisdiction for IFTA reporting
- Monitors Hours of Service (HOS) compliance
- Ensures DOT regulation compliance
- Generates required reports
- Alerts on compliance violations
"""

from datetime import datetime, timedelta
from decimal import Decimal
from time import time
from typing import Any, Optional

from pydantic import BaseModel

from src.agents.base import AgentDecision, BaseAgent


class FuelPurchase(BaseModel):
    """Record of a fuel purchase."""

    timestamp: datetime
    jurisdiction: str  # State/province code (e.g., "OK", "TX")
    gallons: Decimal
    price_per_gallon: Decimal
    total_cost: Decimal
    location: str  # City or address


class MileageRecord(BaseModel):
    """Record of miles driven in a jurisdiction."""

    date: datetime
    jurisdiction: str
    miles: int
    load_id: Optional[str] = None


class IFTAReport(BaseModel):
    """IFTA quarterly report."""

    quarter: str  # e.g., "Q1 2024"
    year: int
    home_jurisdiction: str

    # Jurisdiction-specific data
    jurisdiction_data: dict[str, dict[str, Any]]  # jurisdiction -> {miles, gallons, tax_owed}

    total_miles: int
    total_gallons: Decimal
    total_tax_owed: Decimal
    net_tax_due: Decimal  # Can be negative (refund)

    generated_at: datetime


class HOSStatus(BaseModel):
    """Hours of Service status."""

    driver_id: str
    current_status: str  # "driving", "on_duty", "off_duty", "sleeper"
    hours_driven_today: float
    hours_on_duty_today: float
    hours_available_to_drive: float
    hours_until_required_break: float
    violations: list[str]
    warnings: list[str]


class ComplianceResult(BaseModel):
    """Result of compliance check."""

    timestamp: datetime
    compliance_type: str  # "ifta", "hos", "dot_inspection"
    status: str  # "compliant", "warning", "violation"
    findings: list[str]
    recommendations: list[str]
    execution_time_seconds: float


class ComplianceAgent(BaseAgent):
    """
    Compliance Agent for IFTA, HOS, and DOT compliance tracking.

    Uses LLM for:
    - Analyzing complex compliance scenarios
    - Interpreting regulations
    - Providing actionable recommendations
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the compliance agent."""
        super().__init__(agent_name="compliance", **kwargs)

        # Load configuration
        business_config = self.config_manager.business_config
        self.home_jurisdiction = business_config.get("ifta", {}).get("home_state", "OK")
        self.company_info = self.config_manager.get_company_info()

    def calculate_ifta_report(
        self,
        fuel_purchases: list[FuelPurchase],
        mileage_records: list[MileageRecord],
        quarter: str,
        year: int,
    ) -> IFTAReport:
        """
        Calculate IFTA quarterly report.

        Args:
            fuel_purchases: List of fuel purchases for the quarter
            mileage_records: List of mileage records by jurisdiction
            quarter: Quarter identifier (e.g., "Q1")
            year: Year

        Returns:
            IFTAReport with tax calculations
        """
        start_time = time()

        self.logger.info(
            "calculating_ifta_report",
            quarter=quarter,
            year=year,
            fuel_records=len(fuel_purchases),
            mileage_records=len(mileage_records),
        )

        # Aggregate data by jurisdiction
        jurisdiction_data: dict[str, dict[str, Any]] = {}

        # Sum miles by jurisdiction
        for record in mileage_records:
            if record.jurisdiction not in jurisdiction_data:
                jurisdiction_data[record.jurisdiction] = {
                    "miles": 0,
                    "gallons": Decimal("0"),
                    "fuel_cost": Decimal("0"),
                }
            jurisdiction_data[record.jurisdiction]["miles"] += record.miles

        # Sum fuel purchases by jurisdiction
        for purchase in fuel_purchases:
            if purchase.jurisdiction not in jurisdiction_data:
                jurisdiction_data[purchase.jurisdiction] = {
                    "miles": 0,
                    "gallons": Decimal("0"),
                    "fuel_cost": Decimal("0"),
                }
            jurisdiction_data[purchase.jurisdiction]["gallons"] += purchase.gallons
            jurisdiction_data[purchase.jurisdiction]["fuel_cost"] += purchase.total_cost

        # Calculate totals
        total_miles = sum(data["miles"] for data in jurisdiction_data.values())
        total_gallons = sum(data["gallons"] for data in jurisdiction_data.values())

        # Calculate tax owed per jurisdiction
        # This is a simplified calculation - real IFTA is more complex
        total_tax_owed = Decimal("0")

        for jurisdiction, data in jurisdiction_data.items():
            miles = data["miles"]
            gallons = data["gallons"]

            if total_miles > 0:
                # MPG for this jurisdiction
                mpg = Decimal(str(total_miles)) / total_gallons if total_gallons > 0 else Decimal("0")

                # Gallons consumed in this jurisdiction
                taxable_gallons = Decimal(str(miles)) / mpg if mpg > 0 else Decimal("0")

                # Tax rate (simplified - would need actual tax rates by jurisdiction)
                tax_rate = self._get_fuel_tax_rate(jurisdiction)

                # Tax owed = (taxable_gallons - purchased_gallons) * tax_rate
                tax_owed = (taxable_gallons - gallons) * tax_rate

                data["taxable_gallons"] = taxable_gallons
                data["tax_rate"] = tax_rate
                data["tax_owed"] = tax_owed
                total_tax_owed += tax_owed

        report = IFTAReport(
            quarter=f"{quarter} {year}",
            year=year,
            home_jurisdiction=self.home_jurisdiction,
            jurisdiction_data=jurisdiction_data,
            total_miles=total_miles,
            total_gallons=total_gallons,
            total_tax_owed=total_tax_owed,
            net_tax_due=total_tax_owed,  # Simplified
            generated_at=datetime.now(),
        )

        # Log decision
        decision = AgentDecision(
            timestamp=datetime.now(),
            agent_name=self.agent_name,
            decision_type="ifta_calculation",
            input_data={
                "quarter": quarter,
                "year": year,
                "jurisdictions": list(jurisdiction_data.keys()),
            },
            reasoning=f"Calculated IFTA for {len(jurisdiction_data)} jurisdictions",
            confidence=1.0,  # Mathematical calculation, high confidence
            output_data={
                "total_miles": total_miles,
                "total_tax_owed": float(total_tax_owed),
            },
            tools_used=["ifta_calculator", "tax_rate_lookup"],
            execution_time_seconds=time() - start_time,
        )
        self.log_decision(decision)

        return report

    def check_hos_compliance(
        self,
        driver_id: str,
        current_status: str,
        drive_hours_today: float,
        on_duty_hours_today: float,
        last_break_time: Optional[datetime] = None,
    ) -> HOSStatus:
        """
        Check Hours of Service compliance.

        Args:
            driver_id: Driver identifier
            current_status: Current duty status
            drive_hours_today: Hours driven today
            on_duty_hours_today: Hours on duty today
            last_break_time: Time of last break

        Returns:
            HOSStatus with compliance information
        """
        violations = []
        warnings = []

        # HOS limits (simplified - actual rules are more complex)
        MAX_DRIVE_HOURS = 11.0
        MAX_ON_DUTY_HOURS = 14.0
        REQUIRED_BREAK_AFTER = 8.0

        # Check driving hours
        hours_available_to_drive = MAX_DRIVE_HOURS - drive_hours_today
        if drive_hours_today >= MAX_DRIVE_HOURS:
            violations.append(f"Maximum driving hours ({MAX_DRIVE_HOURS}h) exceeded")
        elif drive_hours_today >= MAX_DRIVE_HOURS * 0.9:
            warnings.append(f"Approaching maximum driving hours ({hours_available_to_drive:.1f}h remaining)")

        # Check on-duty hours
        if on_duty_hours_today >= MAX_ON_DUTY_HOURS:
            violations.append(f"Maximum on-duty hours ({MAX_ON_DUTY_HOURS}h) exceeded")
        elif on_duty_hours_today >= MAX_ON_DUTY_HOURS * 0.9:
            warnings.append(f"Approaching maximum on-duty hours")

        # Check required breaks
        hours_until_break = REQUIRED_BREAK_AFTER
        if last_break_time:
            hours_since_break = (datetime.now() - last_break_time).total_seconds() / 3600
            hours_until_break = REQUIRED_BREAK_AFTER - hours_since_break

            if hours_since_break >= REQUIRED_BREAK_AFTER:
                violations.append(f"Required 30-minute break after {REQUIRED_BREAK_AFTER}h not taken")
            elif hours_since_break >= REQUIRED_BREAK_AFTER * 0.8:
                warnings.append(f"Break required soon ({hours_until_break:.1f}h)")

        status = HOSStatus(
            driver_id=driver_id,
            current_status=current_status,
            hours_driven_today=drive_hours_today,
            hours_on_duty_today=on_duty_hours_today,
            hours_available_to_drive=max(0, hours_available_to_drive),
            hours_until_required_break=max(0, hours_until_break),
            violations=violations,
            warnings=warnings,
        )

        self.logger.info(
            "hos_compliance_check",
            driver_id=driver_id,
            violations=len(violations),
            warnings=len(warnings),
        )

        return status

    def execute(self, compliance_type: str, **kwargs: Any) -> ComplianceResult:
        """
        Execute compliance check.

        Args:
            compliance_type: Type of compliance check ("ifta", "hos", "general")
            **kwargs: Additional arguments specific to compliance type

        Returns:
            ComplianceResult with findings and recommendations
        """
        start_time = time()

        findings = []
        recommendations = []
        status = "compliant"

        if compliance_type == "hos":
            hos_status = self.check_hos_compliance(**kwargs)
            if hos_status.violations:
                status = "violation"
                findings.extend(hos_status.violations)
            elif hos_status.warnings:
                status = "warning"
                findings.extend(hos_status.warnings)
            else:
                findings.append("All HOS requirements met")

            if status != "compliant":
                recommendations.append("Review driver schedules to ensure compliance")
                recommendations.append("Consider implementing automated HOS tracking")

        elif compliance_type == "ifta":
            # General IFTA compliance check
            findings.append("IFTA tracking active")
            recommendations.append("Ensure all fuel receipts are retained")
            recommendations.append("Track miles by jurisdiction accurately")

        result = ComplianceResult(
            timestamp=datetime.now(),
            compliance_type=compliance_type,
            status=status,
            findings=findings,
            recommendations=recommendations,
            execution_time_seconds=time() - start_time,
        )

        return result

    def _get_fuel_tax_rate(self, jurisdiction: str) -> Decimal:
        """
        Get fuel tax rate for a jurisdiction.

        This is simplified - real implementation would query current tax rates.
        """
        # Simplified tax rates (actual rates vary and change)
        tax_rates = {
            "OK": Decimal("0.20"),
            "TX": Decimal("0.20"),
            "AR": Decimal("0.245"),
            "KS": Decimal("0.26"),
            "MO": Decimal("0.195"),
            "LA": Decimal("0.20"),
        }
        return tax_rates.get(jurisdiction, Decimal("0.20"))  # Default to $0.20/gallon


def main() -> None:
    """Example usage of the compliance agent."""
    import structlog

    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
    )

    # Create agent
    agent = ComplianceAgent()

    # Example: HOS compliance check
    print("\n" + "=" * 80)
    print("HOS COMPLIANCE CHECK")
    print("=" * 80)

    hos_status = agent.check_hos_compliance(
        driver_id="DRV-001",
        current_status="driving",
        drive_hours_today=9.5,
        on_duty_hours_today=11.0,
        last_break_time=datetime.now() - timedelta(hours=7),
    )

    print(f"Driver: {hos_status.driver_id}")
    print(f"Status: {hos_status.current_status}")
    print(f"Hours Driven: {hos_status.hours_driven_today:.1f}h")
    print(f"Hours Available: {hos_status.hours_available_to_drive:.1f}h")
    print()

    if hos_status.violations:
        print("VIOLATIONS:")
        for v in hos_status.violations:
            print(f"  ⚠️  {v}")
        print()

    if hos_status.warnings:
        print("WARNINGS:")
        for w in hos_status.warnings:
            print(f"  ⚡ {w}")
        print()

    # Example: IFTA report
    print("=" * 80)
    print("IFTA REPORT")
    print("=" * 80)

    fuel_purchases = [
        FuelPurchase(
            timestamp=datetime.now(),
            jurisdiction="OK",
            gallons=Decimal("25.5"),
            price_per_gallon=Decimal("3.45"),
            total_cost=Decimal("87.98"),
            location="Tulsa, OK",
        ),
        FuelPurchase(
            timestamp=datetime.now(),
            jurisdiction="TX",
            gallons=Decimal("28.0"),
            price_per_gallon=Decimal("3.60"),
            total_cost=Decimal("100.80"),
            location="Dallas, TX",
        ),
    ]

    mileage_records = [
        MileageRecord(date=datetime.now(), jurisdiction="OK", miles=450),
        MileageRecord(date=datetime.now(), jurisdiction="TX", miles=350),
        MileageRecord(date=datetime.now(), jurisdiction="AR", miles=200),
    ]

    report = agent.calculate_ifta_report(
        fuel_purchases=fuel_purchases,
        mileage_records=mileage_records,
        quarter="Q1",
        year=2024,
    )

    print(f"Quarter: {report.quarter}")
    print(f"Total Miles: {report.total_miles:,}")
    print(f"Total Gallons: {report.total_gallons:.1f}")
    print(f"Net Tax Due: ${report.net_tax_due:.2f}")
    print()
    print("By Jurisdiction:")
    for jurisdiction, data in report.jurisdiction_data.items():
        print(f"  {jurisdiction}:")
        print(f"    Miles: {data['miles']:,}")
        print(f"    Fuel Purchased: {data['gallons']:.1f} gal")
        if "tax_owed" in data:
            print(f"    Tax: ${data['tax_owed']:.2f}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
