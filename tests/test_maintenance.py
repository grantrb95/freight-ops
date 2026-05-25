"""Tests for vehicle maintenance tracking models and the maintenance agent."""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from src.agents.maintenance import MaintenanceAgent
from src.data.models.maintenance import (
    EquipmentCategory,
    MaintenanceRecord,
    MaintenanceSchedule,
    MaintenanceStatus,
    MaintenanceType,
    ServiceInterval,
)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@pytest.mark.unit
class TestServiceInterval:
    def test_miles_only_is_valid(self) -> None:
        interval = ServiceInterval(miles=7500)
        assert interval.miles == 7500
        assert interval.months is None

    def test_months_only_is_valid(self) -> None:
        interval = ServiceInterval(months=12)
        assert interval.months == 12

    def test_requires_at_least_one_dimension(self) -> None:
        with pytest.raises(ValueError):
            ServiceInterval()


@pytest.mark.unit
class TestMaintenanceSchedule:
    def _oil_change(self, **overrides: object) -> MaintenanceSchedule:
        defaults: dict[str, object] = {
            "unit_id": "truck",
            "equipment": EquipmentCategory.TRUCK,
            "maintenance_type": MaintenanceType.OIL_CHANGE,
            "interval": ServiceInterval(miles=7500, months=6),
            "last_service_date": datetime(2026, 1, 1),
            "last_service_odometer": 100_000,
        }
        defaults.update(overrides)
        return MaintenanceSchedule(**defaults)  # type: ignore[arg-type]

    def test_next_due_computations(self) -> None:
        sched = self._oil_change()
        assert sched.next_due_odometer == 107_500
        assert sched.next_due_date == datetime(2026, 7, 1)

    def test_next_due_none_without_baseline(self) -> None:
        sched = self._oil_change(last_service_date=None, last_service_odometer=None)
        assert sched.next_due_odometer is None
        assert sched.next_due_date is None

    def test_remaining(self) -> None:
        sched = self._oil_change()
        assert sched.miles_remaining(105_000) == 2_500
        assert sched.days_remaining(datetime(2026, 6, 21)) == 10

    def test_status_ok(self) -> None:
        sched = self._oil_change()
        # Well within both mileage and time windows.
        assert sched.evaluate(101_000, datetime(2026, 2, 1)) == MaintenanceStatus.OK

    def test_status_due_soon_by_miles(self) -> None:
        sched = self._oil_change()
        # 300 miles remaining (<= 500 threshold), but plenty of time left.
        assert sched.evaluate(107_200, datetime(2026, 2, 1)) == MaintenanceStatus.DUE_SOON

    def test_status_due_soon_by_days(self) -> None:
        sched = self._oil_change()
        # Plenty of miles left, but within the 14-day window.
        assert sched.evaluate(101_000, datetime(2026, 6, 25)) == MaintenanceStatus.DUE_SOON

    def test_status_overdue_by_miles(self) -> None:
        sched = self._oil_change()
        assert sched.evaluate(108_000, datetime(2026, 2, 1)) == MaintenanceStatus.OVERDUE

    def test_status_overdue_by_days(self) -> None:
        sched = self._oil_change()
        assert sched.evaluate(101_000, datetime(2026, 8, 1)) == MaintenanceStatus.OVERDUE

    def test_status_overdue_wins_over_due_soon(self) -> None:
        sched = self._oil_change()
        # Overdue on miles even though time is fine -> overdue.
        assert sched.evaluate(200_000, datetime(2026, 2, 1)) == MaintenanceStatus.OVERDUE

    def test_no_baseline_is_due_soon(self) -> None:
        sched = self._oil_change(last_service_date=None, last_service_odometer=None)
        assert sched.evaluate(105_000, datetime(2026, 2, 1)) == MaintenanceStatus.DUE_SOON

    def test_apply_service_updates_baseline(self) -> None:
        sched = self._oil_change()
        record = MaintenanceRecord(
            record_id="r1",
            unit_id="truck",
            equipment=EquipmentCategory.TRUCK,
            maintenance_type=MaintenanceType.OIL_CHANGE,
            service_date=datetime(2026, 7, 1),
            odometer=107_500,
            cost=Decimal("129.99"),
        )
        sched.apply_service(record)
        assert sched.last_service_odometer == 107_500
        assert sched.next_due_odometer == 115_000


@pytest.mark.unit
class TestMaintenanceRecord:
    def test_record_defaults(self) -> None:
        record = MaintenanceRecord(
            record_id="r1",
            unit_id="truck",
            equipment=EquipmentCategory.TRUCK,
            maintenance_type=MaintenanceType.TIRE_ROTATION,
            service_date=datetime(2026, 5, 1),
            odometer=100_000,
        )
        assert record.cost == Decimal("0")
        assert record.vendor is None

    def test_negative_cost_rejected(self) -> None:
        with pytest.raises(ValueError):
            MaintenanceRecord(
                record_id="r1",
                unit_id="truck",
                equipment=EquipmentCategory.TRUCK,
                maintenance_type=MaintenanceType.OIL_CHANGE,
                service_date=datetime(2026, 5, 1),
                odometer=100_000,
                cost=Decimal("-5"),
            )


@pytest.mark.unit
class TestMaintenanceAgent:
    def _agent(self) -> MaintenanceAgent:
        schedules = [
            MaintenanceSchedule(
                unit_id="truck",
                equipment=EquipmentCategory.TRUCK,
                maintenance_type=MaintenanceType.OIL_CHANGE,
                interval=ServiceInterval(miles=7500, months=6),
                last_service_date=datetime(2026, 1, 1),
                last_service_odometer=100_000,
            ),
            MaintenanceSchedule(
                unit_id="truck",
                equipment=EquipmentCategory.TRUCK,
                maintenance_type=MaintenanceType.DOT_INSPECTION,
                interval=ServiceInterval(months=12),
                last_service_date=datetime(2025, 6, 1),
                last_service_odometer=80_000,
            ),
            MaintenanceSchedule(
                unit_id="trailer",
                equipment=EquipmentCategory.TRAILER,
                maintenance_type=MaintenanceType.WHEEL_BEARING,
                interval=ServiceInterval(miles=12000, months=12),
                last_service_date=datetime(2026, 1, 1),
                last_service_odometer=40_000,
            ),
        ]
        return MaintenanceAgent(schedules)

    def test_evaluate_fleet_returns_alert_per_schedule(self) -> None:
        agent = self._agent()
        alerts = agent.evaluate_fleet(
            {"truck": 108_000, "trailer": 45_000}, as_of=datetime(2026, 5, 24)
        )
        assert len(alerts) == 3

    def test_alerts_sorted_most_urgent_first(self) -> None:
        agent = self._agent()
        alerts = agent.evaluate_fleet(
            {"truck": 108_000, "trailer": 45_000}, as_of=datetime(2026, 5, 24)
        )
        # Truck oil change is overdue (108k > 107.5k due); DOT inspection within
        # the 14-day window of its 2026-06-01 due date. Overdue must come first.
        assert alerts[0].status == MaintenanceStatus.OVERDUE
        assert alerts[0].maintenance_type == MaintenanceType.OIL_CHANGE

    def test_due_items_excludes_ok(self) -> None:
        agent = self._agent()
        # DOT inspection is due 2026-06-01; at 2026-06-15 it is overdue while the
        # oil change (due 2026-07-01) and trailer bearing (2027-01-01) are still OK.
        due = agent.due_items({"truck": 101_000, "trailer": 41_000}, as_of=datetime(2026, 6, 15))
        assert [a.maintenance_type for a in due] == [MaintenanceType.DOT_INSPECTION]
        assert due[0].status == MaintenanceStatus.OVERDUE

    def test_decisions_logged_for_flagged_items(self) -> None:
        agent = self._agent()
        agent.evaluate_fleet({"truck": 108_000, "trailer": 45_000}, as_of=datetime(2026, 5, 24))
        # Only non-OK items produce decisions.
        assert len(agent.decisions) >= 1
        assert all(d.agent == "maintenance" for d in agent.decisions)

    def test_run_uses_last_odometer_when_reading_missing(self) -> None:
        agent = self._agent()
        # No reading provided -> falls back to last_service_odometer; not overdue on miles.
        alerts = agent.run({}, as_of=datetime(2026, 2, 1))
        truck_oil = next(
            a for a in alerts if a.maintenance_type == MaintenanceType.OIL_CHANGE
        )
        assert truck_oil.status == MaintenanceStatus.OK


@pytest.mark.unit
class TestConfigWiring:
    def test_config_yaml_is_valid_and_has_maintenance(self) -> None:
        config = yaml.safe_load((CONFIG_DIR / "config.yaml").read_text())
        assert "maintenance" in config
        maint = config["maintenance"]
        assert "schedules" in maint
        assert "truck" in maint["schedules"]
        assert "trailer" in maint["schedules"]
        # Every schedule entry must define at least one interval dimension.
        for items in maint["schedules"].values():
            for item in items:
                assert "type" in item
                assert "miles" in item or "months" in item

    def test_llms_json_has_maintenance_agent(self) -> None:
        llms = json.loads((CONFIG_DIR / "llms.json").read_text())
        assert "maintenance" in llms["agent_assignments"]
