"""Tests for the maintenance CLI entrypoint (scripts/run_maintenance.py)."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts.run_maintenance import (
    build_report,
    main,
    render_json,
    render_text,
)
from src.core.config import load_config
from src.data.models.maintenance import (
    MaintenanceAlert,
    MaintenanceStatus,
    MaintenanceType,
    VerificationStatus,
)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.yaml"
AS_OF = datetime(2026, 5, 25)


@pytest.fixture
def config() -> dict:
    return load_config(CONFIG_PATH)


def _alert(alerts: list[MaintenanceAlert], unit: str, mtype: MaintenanceType) -> MaintenanceAlert:
    return next(a for a in alerts if a.unit_id == unit and a.maintenance_type is mtype)


@pytest.mark.unit
class TestGroundTruth:
    """The seed data + 29,503 mi odometer MUST produce these three overdue items."""

    @pytest.mark.parametrize(
        "mtype",
        [MaintenanceType.OIL_CHANGE, MaintenanceType.FUEL_FILTER, MaintenanceType.TIRE_ROTATION],
    )
    def test_expected_overdue(self, config: dict, mtype: MaintenanceType) -> None:
        report = build_report(config, AS_OF)
        alert = _alert(report.alerts, "truck", mtype)
        assert alert.status is MaintenanceStatus.OVERDUE

    def test_overdue_mileage_amounts(self, config: dict) -> None:
        report = build_report(config, AS_OF)
        # Current odometer 29,503; last-service odometers from the seed history.
        assert _alert(report.alerts, "truck", MaintenanceType.OIL_CHANGE).miles_remaining == -8163
        assert _alert(report.alerts, "truck", MaintenanceType.FUEL_FILTER).miles_remaining == -6442
        assert _alert(report.alerts, "truck", MaintenanceType.TIRE_ROTATION).miles_remaining == -11286


@pytest.mark.unit
class TestVerificationAndWarranty:
    def test_seed_records_are_provisional(self, config: dict) -> None:
        report = build_report(config, AS_OF)
        oil = _alert(report.alerts, "truck", MaintenanceType.OIL_CHANGE)
        assert oil.verification_status is VerificationStatus.PROVISIONAL

    def test_unseeded_items_are_unverified(self, config: dict) -> None:
        report = build_report(config, AS_OF)
        air = _alert(report.alerts, "truck", MaintenanceType.AIR_FILTER)
        assert air.verification_status is VerificationStatus.UNVERIFIED

    def test_warranty_critical_flagged(self, config: dict) -> None:
        report = build_report(config, AS_OF)
        assert _alert(report.alerts, "truck", MaintenanceType.FUEL_FILTER).warranty_critical is True
        assert _alert(report.alerts, "truck", MaintenanceType.TRANSMISSION_SERVICE).warranty_critical is True

    def test_routine_items_not_warranty_critical(self, config: dict) -> None:
        report = build_report(config, AS_OF)
        assert _alert(report.alerts, "truck", MaintenanceType.OIL_CHANGE).warranty_critical is False
        assert _alert(report.alerts, "truck", MaintenanceType.TIRE_ROTATION).warranty_critical is False


@pytest.mark.unit
class TestStaleOdometer:
    def test_not_stale_on_verification_day(self, config: dict) -> None:
        report = build_report(config, AS_OF)
        assert report.stale_units == []

    def test_stale_after_threshold(self, config: dict) -> None:
        report = build_report(config, datetime(2026, 6, 10))  # 16 days later
        assert "truck" in report.stale_units
        assert "STALE" in render_text(report)


@pytest.mark.unit
class TestRenderText:
    def test_contains_status_groups_and_legend(self, config: dict) -> None:
        text = render_text(build_report(config, AS_OF))
        assert "OVERDUE (3)" in text
        assert "DUE SOON (6)" in text
        assert "OK (2)" in text

    def test_marks_provisional_and_warranty(self, config: dict) -> None:
        text = render_text(build_report(config, AS_OF))
        assert "[?]" in text
        assert "[warranty: dealer]" in text
        assert "WARRANTY-CRITICAL" in text

    def test_no_trailing_whitespace(self, config: dict) -> None:
        text = render_text(build_report(config, AS_OF))
        assert all(line == line.rstrip() for line in text.splitlines())


@pytest.mark.unit
class TestRenderJson:
    def test_valid_json_with_summary(self, config: dict) -> None:
        payload = json.loads(render_json(build_report(config, AS_OF)))
        assert payload["summary"] == {
            "overdue": 3,
            "due_soon": 6,
            "ok": 2,
            "warranty_critical_due": 3,
        }
        assert len(payload["alerts"]) == 11


@pytest.mark.unit
class TestMain:
    def test_json_format_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["--config", str(CONFIG_PATH), "--as-of", "2026-05-25", "--format", "json"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["summary"]["overdue"] == 3

    def test_text_format_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["--config", str(CONFIG_PATH), "--as-of", "2026-05-25"])
        assert rc == 0
        assert "Fleet Maintenance Report" in capsys.readouterr().out
