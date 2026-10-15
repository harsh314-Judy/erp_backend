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
