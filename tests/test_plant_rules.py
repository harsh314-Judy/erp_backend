from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.api.routes.invoice.gst import claim, financial_year, split_gst
from app.api.routes.production.job_flow import next_status
from app.api.security.permissions import (
    MANAGE_ADMINS,
    VIEW_FINANCIALS,
    VIEW_SUPPLIERS,
    can_manage_role,
    can_see_prices,
    role_has,
)


def test_permission_matrix() -> None:
    assert role_has("super_admin", MANAGE_ADMINS)
    assert not role_has("admin", MANAGE_ADMINS)
    assert role_has("admin", VIEW_FINANCIALS)
    assert not role_has("accountant", VIEW_FINANCIALS)
    assert role_has("accountant", VIEW_SUPPLIERS)
    assert not role_has("staff", VIEW_SUPPLIERS)
    assert not can_see_prices("staff")
    assert can_see_prices("accountant")
    assert can_manage_role("super_admin", "admin")
    assert not can_manage_role("admin", "admin")
    assert not can_manage_role("admin", "super_admin")
    assert can_manage_role("admin", "accountant")
    assert can_manage_role("admin", "staff")
    assert not can_manage_role("accountant", "staff")


def test_competing_holds() -> None:
    held, short = claim("10", "4")
    assert held == Decimal("4.000")
    assert short == Decimal("0.000")
    held, short = claim("3.5", "8")
    assert held == Decimal("3.500")
    assert short == Decimal("4.500")
    with pytest.raises(ValueError):
        claim("-1", "1")


def test_job_lifecycle() -> None:
    assert next_status("pending", "start") == "in_progress"
    assert next_status("in_progress", "await_approval") == "awaiting_approval"
    assert next_status("awaiting_approval", "approve") == "completed"
    assert next_status("pending", "cancel") == "cancelled"
    assert next_status("in_progress", "cancel") == "cancelled"
    with pytest.raises(ValueError):
        next_status("completed", "start")
    with pytest.raises(ValueError):
        next_status("pending", "approve")


def test_floor_totals_keep_units_and_shared_batches() -> None:
    from app.api.routes.floor.floor_aggregate import (
        FloorFact,
        department_average,
        department_rollup,
        worker_rollup,
    )

    day = datetime(2026, 11, 12).date()
    shared = FloorFact(
        entry_id="1",
        operation_id="assembly",
        entry_date=day,
        output_name="Thali",
        output_unit="pcs",
        output_quantity=Decimal("300"),
        scrap_quantity=Decimal("0"),
        scrap_unit=None,
        input_quantity=None,
        input_unit=None,
        worker_ids=("raj", "amit"),
    )
    cut = FloorFact(
        entry_id="2",
        operation_id="cutting",
        entry_date=day,
        output_name="Sheet",
        output_unit="kg",
        output_quantity=Decimal("100"),
        scrap_quantity=Decimal("2"),
        scrap_unit="pcs",
        input_quantity=Decimal("110"),
        input_unit="kg",
        worker_ids=("raj",),
    )
    department = department_rollup([shared])
    assert department.output == {"pcs": Decimal("300")}
    assert department.entries == 1
    assert worker_rollup([shared], "raj").output["pcs"] == Decimal("300")
    assert worker_rollup([shared], "amit").output["pcs"] == Decimal("300")
    mixed = department_rollup([shared, cut])
    assert mixed.output["pcs"] == Decimal("300")
    assert mixed.output["kg"] == Decimal("100")
    assert "410" not in {str(value) for value in mixed.output.values()}
    assert mixed.scrap == {"pcs": Decimal("2")}
    assert mixed.scrap_pct["kg"] is None
    matched = department_rollup(
        [
            FloorFact(
                entry_id="3",
                operation_id="cutting",
                entry_date=day,
                output_name="Sheet",
                output_unit="kg",
                output_quantity=Decimal("100"),
                scrap_quantity=Decimal("10"),
                scrap_unit="kg",
                input_quantity=None,
                input_unit=None,
                worker_ids=("raj",),
            )
        ]
    )
    assert matched.scrap_pct["kg"] == Decimal("10.00")
    average = department_average([shared], "assembly")
    assert average["pcs"] == Decimal("300.000")


def test_gst_and_financial_year() -> None:
    cgst, sgst, igst = split_gst(18, "100", same_state=True)
    assert cgst == Decimal("9.00")
    assert sgst == Decimal("9.00")
    assert igst == Decimal("0.00")
    cgst, sgst, igst = split_gst(18, "10.01", same_state=True)
    assert cgst + sgst == Decimal("1.80")
    assert igst == Decimal("0.00")
    cgst, sgst, igst = split_gst(18, "100", same_state=False)
    assert (cgst, sgst, igst) == (Decimal("0.00"), Decimal("0.00"), Decimal("18.00"))
    kolkata = ZoneInfo("Asia/Kolkata")
    assert financial_year(datetime(2026, 3, 31, tzinfo=kolkata)) == "2025-26"
    assert financial_year(datetime(2026, 4, 1, tzinfo=kolkata)) == "2026-27"
