"""
Settlement Agent - Automated driver pay calculations.

This agent:
- Calculates driver settlements based on contractual terms
- Tracks advances, deductions, and reimbursements
- Ensures accurate and timely driver payments
- Generates detailed settlement reports
- Maintains compliance with owner-operator agreements
"""

from datetime import datetime
from decimal import Decimal
from time import time
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.agents.base import AgentDecision, BaseAgent
from src.data.models.load import Load


class DriverContract(BaseModel):
    """Driver/owner-operator contract terms."""

    driver_id: str
    driver_name: str
    pay_type: str  # "percentage" or "per_mile"
    pay_rate: Decimal  # Either percentage (0.0-1.0) or dollar amount per mile
    fuel_card_provided: bool = False
    insurance_deduction: Decimal = Decimal("0")
    weekly_deductions: Decimal = Decimal("0")


class Advance(BaseModel):
    """Cash advance given to driver."""

    advance_id: str
    driver_id: str
    amount: Decimal
    date: datetime
    reason: str


class Expense(BaseModel):
    """Expense to be reimbursed or deducted."""

    expense_id: str
    driver_id: str
    expense_type: str  # "fuel", "tolls", "maintenance", "other"
    amount: Decimal
    date: datetime
    description: str
    reimbursable: bool = True


class LoadSettlement(BaseModel):
    """Settlement calculation for a single load."""

    load_id: str
    gross_revenue: Decimal
    driver_gross_pay: Decimal
    calculation_method: str
    notes: str


class DriverSettlement(BaseModel):
    """Complete settlement for a driver for a period."""

    settlement_id: str
    driver_id: str
    driver_name: str
    period_start: datetime
    period_end: datetime

    # Loads and earnings
    loads: list[LoadSettlement]
    total_loads: int
    total_miles: int
    gross_earnings: Decimal

    # Deductions
    advances: list[Advance]
    total_advances: Decimal
    expenses: list[Expense]
    total_expenses: Decimal
    insurance_deduction: Decimal
    other_deductions: Decimal
    total_deductions: Decimal

    # Reimbursements
    reimbursements: list[Expense]
    total_reimbursements: Decimal

    # Final calculation
    net_pay: Decimal
    pay_status: str  # "owed_to_driver", "driver_owes", "settled"

    generated_at: datetime
    notes: list[str] = Field(default_factory=list)


class SettlementAgent(BaseAgent):
    """
    Settlement Agent for driver pay calculations.

    Uses LLM for:
    - Interpreting complex contract terms
    - Identifying discrepancies
    - Providing explanations for drivers
    - Suggesting payment optimizations
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the settlement agent."""
        super().__init__(agent_name="settlement", **kwargs)

    def calculate_settlement(
        self,
        driver_contract: DriverContract,
        loads: list[Load],
        advances: Optional[list[Advance]] = None,
        expenses: Optional[list[Expense]] = None,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> DriverSettlement:
        """
        Calculate driver settlement for a period.

        Args:
            driver_contract: Driver's contract terms
            loads: Loads completed in the period
            advances: Cash advances given
            expenses: Expenses to process
            period_start: Settlement period start
            period_end: Settlement period end

        Returns:
            DriverSettlement with complete calculation
        """
        start_time = time()

        advances = advances or []
        expenses = expenses or []
        period_start = period_start or datetime.now()
        period_end = period_end or datetime.now()

        self.logger.info(
            "calculating_settlement",
            driver_id=driver_contract.driver_id,
            loads=len(loads),
            advances=len(advances),
            expenses=len(expenses),
        )

        # Calculate earnings from loads
        load_settlements = []
        gross_earnings = Decimal("0")
        total_miles = 0

        for load in loads:
            settlement = self._calculate_load_settlement(load, driver_contract)
            load_settlements.append(settlement)
            gross_earnings += settlement.driver_gross_pay
            total_miles += load.loaded_miles

        # Calculate deductions
        total_advances = sum(a.amount for a in advances)

        # Separate reimbursable vs deductible expenses
        deductible_expenses = [e for e in expenses if not e.reimbursable]
        reimbursable_expenses = [e for e in expenses if e.reimbursable]

        total_expenses = sum(e.amount for e in deductible_expenses)
        total_reimbursements = sum(e.amount for e in reimbursable_expenses)

        # Insurance and other deductions
        insurance_deduction = driver_contract.insurance_deduction
        other_deductions = driver_contract.weekly_deductions

        total_deductions = (
            total_advances + total_expenses + insurance_deduction + other_deductions
        )

        # Calculate net pay
        net_pay = gross_earnings - total_deductions + total_reimbursements

        # Determine pay status
        if net_pay > 0:
            pay_status = "owed_to_driver"
        elif net_pay < 0:
            pay_status = "driver_owes"
        else:
            pay_status = "settled"

        # Generate notes
        notes = self._generate_settlement_notes(
            driver_contract, gross_earnings, total_deductions, net_pay
        )

        settlement = DriverSettlement(
            settlement_id=f"SETTLE-{driver_contract.driver_id}-{datetime.now().strftime('%Y%m%d')}",
            driver_id=driver_contract.driver_id,
            driver_name=driver_contract.driver_name,
            period_start=period_start,
            period_end=period_end,
            loads=load_settlements,
            total_loads=len(loads),
            total_miles=total_miles,
            gross_earnings=gross_earnings,
            advances=advances,
            total_advances=total_advances,
            expenses=deductible_expenses,
            total_expenses=total_expenses,
            insurance_deduction=insurance_deduction,
            other_deductions=other_deductions,
            total_deductions=total_deductions,
            reimbursements=reimbursable_expenses,
            total_reimbursements=total_reimbursements,
            net_pay=net_pay,
            pay_status=pay_status,
            generated_at=datetime.now(),
            notes=notes,
        )

        # Log decision
        decision = AgentDecision(
            timestamp=datetime.now(),
            agent_name=self.agent_name,
            decision_type="settlement_calculation",
            input_data={
                "driver_id": driver_contract.driver_id,
                "loads": len(loads),
            },
            reasoning=f"Calculated settlement for {len(loads)} loads",
            confidence=1.0,  # Mathematical calculation
            output_data={
                "gross_earnings": float(gross_earnings),
                "net_pay": float(net_pay),
                "pay_status": pay_status,
            },
            tools_used=["settlement_calculator", "contract_interpreter"],
            execution_time_seconds=time() - start_time,
        )
        self.log_decision(decision)

        return settlement

    def execute(self, *args: Any, **kwargs: Any) -> DriverSettlement:
        """
        Execute settlement calculation (delegates to calculate_settlement).

        Args:
            *args: Positional arguments for calculate_settlement
            **kwargs: Keyword arguments for calculate_settlement

        Returns:
            DriverSettlement
        """
        return self.calculate_settlement(*args, **kwargs)

    def _calculate_load_settlement(
        self, load: Load, contract: DriverContract
    ) -> LoadSettlement:
        """Calculate driver pay for a single load."""
        gross_revenue = load.gross_revenue

        if contract.pay_type == "percentage":
            driver_pay = gross_revenue * contract.pay_rate
            calculation_method = f"{contract.pay_rate * 100:.0f}% of gross revenue"
        elif contract.pay_type == "per_mile":
            driver_pay = Decimal(str(load.loaded_miles)) * contract.pay_rate
            calculation_method = f"${contract.pay_rate}/mile × {load.loaded_miles} miles"
        else:
            driver_pay = Decimal("0")
            calculation_method = "Unknown pay type"

        # If driver has fuel card, fuel surcharge goes to company
        if contract.fuel_card_provided:
            # Fuel surcharge stays with company
            notes = "Fuel surcharge retained (fuel card provided)"
        else:
            # Driver gets fuel surcharge
            driver_pay += load.fuel_surcharge
            notes = "Fuel surcharge included in pay"

        return LoadSettlement(
            load_id=load.load_id,
            gross_revenue=gross_revenue,
            driver_gross_pay=driver_pay,
            calculation_method=calculation_method,
            notes=notes,
        )

    def _generate_settlement_notes(
        self,
        contract: DriverContract,
        gross_earnings: Decimal,
        total_deductions: Decimal,
        net_pay: Decimal,
    ) -> list[str]:
        """Generate helpful notes for the settlement."""
        notes = []

        # Pay rate note
        if contract.pay_type == "percentage":
            notes.append(f"Pay rate: {contract.pay_rate * 100:.0f}% of gross revenue")
        else:
            notes.append(f"Pay rate: ${contract.pay_rate}/mile")

        # Earnings note
        notes.append(f"Gross earnings: ${gross_earnings:.2f}")

        # Deductions note
        if total_deductions > 0:
            notes.append(f"Total deductions: ${total_deductions:.2f}")

        # Net pay note
        if net_pay > 0:
            notes.append(f"Amount owed to driver: ${net_pay:.2f}")
        elif net_pay < 0:
            notes.append(f"Driver owes company: ${abs(net_pay):.2f}")
        else:
            notes.append("Settlement is balanced")

        # Fuel card note
        if contract.fuel_card_provided:
            notes.append("Fuel card provided - fuel surcharges not included in pay")

        return notes


def main() -> None:
    """Example usage of the settlement agent."""
    import structlog
    from src.data.models.load import Location, LoadType

    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
    )

    # Create agent
    agent = SettlementAgent()

    # Example driver contract
    contract = DriverContract(
        driver_id="DRV-001",
        driver_name="John Smith",
        pay_type="percentage",
        pay_rate=Decimal("0.70"),  # 70% of gross revenue
        fuel_card_provided=False,
        insurance_deduction=Decimal("250.00"),
        weekly_deductions=Decimal("0"),
    )

    # Example loads
    loads = [
        Load(
            load_id="LOAD-001",
            broker_name="Test Broker",
            origin=Location(city="Tulsa", state="OK"),
            destination=Location(city="Dallas", state="TX"),
            pickup_date=datetime.now(),
            delivery_date=datetime.now(),
            commodity="Auto Parts",
            weight=5000,
            rate=Decimal("800"),
            fuel_surcharge=Decimal("50"),
            loaded_miles=250,
            deadhead_miles=20,
        ),
        Load(
            load_id="LOAD-002",
            broker_name="Test Broker 2",
            origin=Location(city="Dallas", state="TX"),
            destination=Location(city="Houston", state="TX"),
            pickup_date=datetime.now(),
            delivery_date=datetime.now(),
            commodity="Machinery",
            weight=8000,
            rate=Decimal("600"),
            fuel_surcharge=Decimal("40"),
            loaded_miles=240,
            deadhead_miles=15,
        ),
    ]

    # Example advances
    advances = [
        Advance(
            advance_id="ADV-001",
            driver_id="DRV-001",
            amount=Decimal("200.00"),
            date=datetime.now(),
            reason="Fuel advance",
        )
    ]

    # Example expenses
    expenses = [
        Expense(
            expense_id="EXP-001",
            driver_id="DRV-001",
            expense_type="tolls",
            amount=Decimal("35.00"),
            date=datetime.now(),
            description="Toll roads",
            reimbursable=True,
        ),
        Expense(
            expense_id="EXP-002",
            driver_id="DRV-001",
            expense_type="fuel",
            amount=Decimal("150.00"),
            date=datetime.now(),
            description="Fuel purchase",
            reimbursable=False,
        ),
    ]

    # Calculate settlement
    settlement = agent.calculate_settlement(
        driver_contract=contract,
        loads=loads,
        advances=advances,
        expenses=expenses,
    )

    # Print results
    print("\n" + "=" * 80)
    print("DRIVER SETTLEMENT REPORT")
    print("=" * 80)
    print(f"Settlement ID: {settlement.settlement_id}")
    print(f"Driver: {settlement.driver_name} ({settlement.driver_id})")
    print(f"Period: {settlement.period_start.date()} to {settlement.period_end.date()}")
    print()

    print("EARNINGS:")
    print(f"  Loads Completed: {settlement.total_loads}")
    print(f"  Total Miles: {settlement.total_miles:,}")
    print(f"  Gross Earnings: ${settlement.gross_earnings:.2f}")
    print()

    print("DEDUCTIONS:")
    print(f"  Advances: ${settlement.total_advances:.2f}")
    print(f"  Expenses: ${settlement.total_expenses:.2f}")
    print(f"  Insurance: ${settlement.insurance_deduction:.2f}")
    print(f"  Other: ${settlement.other_deductions:.2f}")
    print(f"  Total Deductions: ${settlement.total_deductions:.2f}")
    print()

    if settlement.total_reimbursements > 0:
        print(f"REIMBURSEMENTS: ${settlement.total_reimbursements:.2f}")
        print()

    print(f"NET PAY: ${settlement.net_pay:.2f}")
    print(f"Status: {settlement.pay_status.upper()}")
    print()

    print("NOTES:")
    for note in settlement.notes:
        print(f"  • {note}")

    print()
    print("LOAD DETAILS:")
    for load_settle in settlement.loads:
        print(f"  {load_settle.load_id}:")
        print(f"    Gross: ${load_settle.gross_revenue:.2f}")
        print(f"    Driver Pay: ${load_settle.driver_gross_pay:.2f}")
        print(f"    Method: {load_settle.calculation_method}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
