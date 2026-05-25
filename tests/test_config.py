"""Tests for configuration loading and the MaintenanceAgent.from_config factory."""

from pathlib import Path

import pytest

from src.agents.maintenance import MaintenanceAgent
from src.core.config import (
    load_config,
    load_maintenance_schedules,
    load_odometers,
    load_service_history,
)
from src.data.models.maintenance import (
    EquipmentCategory,
    MaintenanceType,
    ServiceInterval,
    VerificationStatus,
)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.yaml"

# Truck: oil_change, tire_rotation, fuel_filter, air_filter,
#        transmission_service, coolant_flush, dot_inspection = 7
# Trailer: wheel_bearing, brake_service, tire_replacement, dot_inspection = 4
EXPECTED_SCHEDULE_COUNT = 11


@pytest.mark.unit
class TestLoadConfig:
    def test_returns_mapping_with_maintenance(self) -> None:
        config = load_config(CONFIG_PATH)
        assert isinstance(config, dict)
        assert "maintenance" in config

    def test_non_mapping_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("- just\n- a\n- list\n")
        with pytest.raises(ValueError):
            load_config(bad)


@pytest.mark.unit
class TestLoadMaintenanceSchedules:
    def test_count(self) -> None:
        schedules = load_maintenance_schedules(path=CONFIG_PATH)
        assert len(schedules) == EXPECTED_SCHEDULE_COUNT

    def test_truck_oil_change_parsed(self) -> None:
        schedules = load_maintenance_schedules(path=CONFIG_PATH)
        oil = next(
            s
            for s in schedules
            if s.equipment is EquipmentCategory.TRUCK
            and s.maintenance_type is MaintenanceType.OIL_CHANGE
        )
        assert oil.unit_id == "truck"
        assert oil.interval == ServiceInterval(miles=7500, months=6)
        # Thresholds come from the top-level maintenance config.
        assert oil.due_soon_miles == 500
        assert oil.due_soon_days == 14

    def test_dot_inspection_on_both_units(self) -> None:
        schedules = load_maintenance_schedules(path=CONFIG_PATH)
        dot = [s for s in schedules if s.maintenance_type is MaintenanceType.DOT_INSPECTION]
        assert {s.equipment for s in dot} == {
            EquipmentCategory.TRUCK,
            EquipmentCategory.TRAILER,
        }
        for s in dot:
            assert s.interval.months == 12
            assert s.interval.miles is None

    def test_accepts_preloaded_config(self) -> None:
        config = load_config(CONFIG_PATH)
        schedules = load_maintenance_schedules(config=config)
        assert len(schedules) == EXPECTED_SCHEDULE_COUNT

    def test_unknown_type_raises(self) -> None:
        config = {
            "maintenance": {
                "schedules": {"truck": [{"type": "warp_drive_flush", "miles": 1000}]}
            }
        }
        with pytest.raises(ValueError):
            load_maintenance_schedules(config=config)

    def test_unknown_equipment_raises(self) -> None:
        config = {
            "maintenance": {
                "schedules": {"spaceship": [{"type": "oil_change", "miles": 1000}]}
            }
        }
        with pytest.raises(ValueError):
            load_maintenance_schedules(config=config)

    def test_item_without_interval_raises(self) -> None:
        config = {"maintenance": {"schedules": {"truck": [{"type": "oil_change"}]}}}
        with pytest.raises(ValueError):
            load_maintenance_schedules(config=config)

    def test_missing_maintenance_section_yields_empty(self) -> None:
        assert load_maintenance_schedules(config={}) == []


@pytest.mark.unit
class TestFromConfig:
    def test_builds_agent_with_schedules(self) -> None:
        agent = MaintenanceAgent.from_config(path=CONFIG_PATH)
        assert isinstance(agent, MaintenanceAgent)
        assert len(agent.schedules) == EXPECTED_SCHEDULE_COUNT

    def test_accepts_preloaded_config(self) -> None:
        config = load_config(CONFIG_PATH)
        agent = MaintenanceAgent.from_config(config=config)
        assert len(agent.schedules) == EXPECTED_SCHEDULE_COUNT


@pytest.mark.unit
class TestLoadServiceHistory:
    def test_count_and_provisional(self) -> None:
        records = load_service_history(path=CONFIG_PATH)
        assert len(records) == 5  # 4 truck + 1 trailer seed records
        assert all(r.verification_status is VerificationStatus.PROVISIONAL for r in records)

    def test_oil_change_record(self) -> None:
        records = load_service_history(path=CONFIG_PATH)
        oil = next(r for r in records if r.maintenance_type is MaintenanceType.OIL_CHANGE)
        assert oil.unit_id == "truck"
        assert oil.odometer == 13840

    def test_unknown_verification_raises(self) -> None:
        config = {
            "maintenance": {
                "service_history": [
                    {"unit": "truck", "type": "oil_change", "date": "2026-01-01",
                     "odometer": 1000, "verification": "bogus"}
                ]
            }
        }
        with pytest.raises(ValueError):
            load_service_history(config=config)

    def test_missing_section_yields_empty(self) -> None:
        assert load_service_history(config={}) == []


@pytest.mark.unit
class TestLoadOdometers:
    def test_truck_reading(self) -> None:
        readings = load_odometers(path=CONFIG_PATH)
        assert readings["truck"].miles == 29503
        assert readings["truck"].source == "Motive ELD"
        assert readings["truck"].last_verified_date is not None

    def test_staleness(self) -> None:
        from datetime import datetime

        truck = load_odometers(path=CONFIG_PATH)["truck"]
        assert truck.is_stale(datetime(2026, 5, 25)) is False
        assert truck.is_stale(datetime(2026, 6, 10)) is True

    def test_missing_section_yields_empty(self) -> None:
        assert load_odometers(config={}) == {}


@pytest.mark.unit
class TestHistoryApplication:
    def test_schedule_baseline_seeded_from_history(self) -> None:
        schedules = load_maintenance_schedules(path=CONFIG_PATH)
        oil = next(
            s for s in schedules
            if s.unit_id == "truck" and s.maintenance_type is MaintenanceType.OIL_CHANGE
        )
        assert oil.last_service_odometer == 13840
        assert oil.last_service_verification is VerificationStatus.PROVISIONAL

    def test_apply_history_false_leaves_no_baseline(self) -> None:
        schedules = load_maintenance_schedules(path=CONFIG_PATH, apply_history=False)
        oil = next(
            s for s in schedules
            if s.unit_id == "truck" and s.maintenance_type is MaintenanceType.OIL_CHANGE
        )
        assert oil.last_service_odometer is None

    def test_warranty_critical_set_from_config(self) -> None:
        schedules = load_maintenance_schedules(path=CONFIG_PATH)
        by_type = {(s.unit_id, s.maintenance_type): s for s in schedules}
        assert by_type[("truck", MaintenanceType.FUEL_FILTER)].warranty_critical is True
        assert by_type[("truck", MaintenanceType.OIL_CHANGE)].warranty_critical is False
