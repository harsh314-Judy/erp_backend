from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.config import auth_settings

MONEY = Decimal("0.01")
QTY = Decimal("0.001")


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value)).quantize(MONEY)


def qty(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value)).quantize(QTY)


def financial_year(moment: datetime | None = None) -> str:
    current = moment or datetime.now(ZoneInfo(auth_settings.APP_TIMEZONE))
    if current.tzinfo is None:
        current = current.replace(tzinfo=ZoneInfo(auth_settings.APP_TIMEZONE))
    local = current.astimezone(ZoneInfo(auth_settings.APP_TIMEZONE))
    start = local.year if local.month >= 4 else local.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def split_gst(
    rate: Decimal | int | str,
    taxable: Decimal | int | str,
    *,
    same_state: bool,
) -> tuple[Decimal, Decimal, Decimal]:
    """Return CGST, SGST, and IGST for one taxable amount.

    Intra-state supplies split the tax in half. Any leftover paisa stays on SGST
    so the two halves still add up to the full tax.
    """
    tax = money(Decimal(str(taxable)) * Decimal(str(rate)) / Decimal("100"))
    if tax == 0:
        return money(0), money(0), money(0)
    if same_state:
        cgst = money(tax / 2)
        return cgst, money(tax - cgst), money(0)
    return money(0), money(0), tax


def claim(available: Decimal | int | str, requested: Decimal | int | str) -> tuple[Decimal, Decimal]:
    """Hold what is free and return (held, shortfall)."""
    free = qty(available)
    need = qty(requested)
    if free < 0 or need < 0:
        raise ValueError("quantities cannot be negative")
    held = qty(min(free, need))
    return held, qty(need - held)
