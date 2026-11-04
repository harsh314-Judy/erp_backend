from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.user.user_model import User
from app.api.security.permissions import VIEW_FINANCIALS, can_see_prices, role_has

_IST = ZoneInfo("Asia/Kolkata")


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _qty(value) -> Decimal:
    return Decimal(str(value or 0))


class TradingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def items(self, role_name: str) -> list[dict]:
        prices = can_see_prices(role_name)
        products = (
            await self.session.execute(
                text(
                    """
                    SELECT
                      p.id, p.product_name AS name, p.sku_number AS sku, u.name AS unit,
                      p.quantity AS on_hand,
                      coalesce((SELECT sum(r.quantity) FROM stock_reservations r
                                WHERE r.product_id = p.id AND r.status = 'held'), 0) AS held,
                      p.last_purchase_price,
                      coalesce((SELECT string_agg(s.supplier_company_name, ', ' ORDER BY s.supplier_company_name)
                                FROM product_suppliers ps JOIN suppliers s ON s.id = ps.supplier_id
                                WHERE ps.product_id = p.id), '') AS supplier_names,
                      coalesce((SELECT sum(l.quantity) FROM purchase_order_lines l
                                JOIN purchase_orders o ON o.id = l.purchase_order_id
                                WHERE l.product_id = p.id AND o.stock_received), 0) AS bought_qty,
                      coalesce((SELECT sum(l.quantity) FROM sales_order_lines l
                                JOIN sales_orders o ON o.id = l.sales_order_id
                                WHERE l.product_id = p.id AND o.status IN ('delivered', 'dispatched')), 0) AS sold_qty,
                      coalesce((SELECT sum(l.quantity) FROM purchase_order_lines l
                                JOIN purchase_orders o ON o.id = l.purchase_order_id
                                WHERE l.product_id = p.id AND NOT o.stock_received AND o.status <> 'cancelled'), 0) AS incoming_qty
                    FROM products p
                    LEFT JOIN measurement_units u ON u.id = p.measurement_unit_id
                    WHERE p.product_type = 'purchased'
                    ORDER BY p.product_name
                    """
                )
            )
        ).mappings().all()
        materials = (
            await self.session.execute(
                text(
                    """
                    SELECT
                      m.id, m.name, u.name AS unit, m.quantity AS on_hand,
                      coalesce((SELECT sum(r.quantity) FROM stock_reservations r
                                WHERE r.raw_material_id = m.id AND r.status = 'held'), 0) AS held,
                      m.purchase_price AS last_purchase_price,
                      coalesce((SELECT string_agg(s.supplier_company_name, ', ' ORDER BY s.supplier_company_name)
                                FROM raw_material_suppliers rs JOIN suppliers s ON s.id = rs.supplier_id
                                WHERE rs.raw_material_id = m.id), '') AS supplier_names,
                      coalesce((SELECT sum(l.quantity) FROM purchase_order_lines l
                                JOIN purchase_orders o ON o.id = l.purchase_order_id
                                WHERE l.raw_material_id = m.id AND o.stock_received), 0) AS bought_qty,
                      coalesce((SELECT sum(l.quantity) FROM purchase_order_lines l
                                JOIN purchase_orders o ON o.id = l.purchase_order_id
                                WHERE l.raw_material_id = m.id AND NOT o.stock_received AND o.status <> 'cancelled'), 0) AS incoming_qty
                    FROM raw_materials m
                    LEFT JOIN measurement_units u ON u.id = m.measurement_unit_id
                    ORDER BY m.name
                    """
                )
            )
        ).mappings().all()
        rows: list[dict] = []
        for row in products:
            on_hand = _qty(row["on_hand"])
            held = _qty(row["held"])
            rows.append(
                {
                    "kind": "product",
                    "id": row["id"],
                    "name": row["name"],
                    "sku": row["sku"],
                    "unit": row["unit"],
                    "on_hand": on_hand,
                    "available": max(on_hand - held, Decimal("0")),
                    "supplier_names": row["supplier_names"] or "",
                    "last_purchase_price": _money(row["last_purchase_price"]) if prices else None,
                    "bought_qty": _qty(row["bought_qty"]),
                    "sold_qty": _qty(row["sold_qty"]),
                    "incoming_qty": _qty(row["incoming_qty"]),
                }
            )
        for row in materials:
            on_hand = _qty(row["on_hand"])
            held = _qty(row["held"])
            rows.append(
                {
                    "kind": "raw_material",
                    "id": row["id"],
                    "name": row["name"],
                    "sku": None,
                    "unit": row["unit"],
                    "on_hand": on_hand,
                    "available": max(on_hand - held, Decimal("0")),
                    "supplier_names": row["supplier_names"] or "",
                    "last_purchase_price": _money(row["last_purchase_price"]) if prices else None,
                    "bought_qty": _qty(row["bought_qty"]),
                    "sold_qty": Decimal("0"),
                    "incoming_qty": _qty(row["incoming_qty"]),
                }
            )
        return rows

    async def summary(self, role_name: str, period: str) -> dict:
        if period not in {"month", "all"}:
            raise HTTPException(status_code=400, detail="Period must be month or all")
        start = _period_start(period)
        sold = (
            await self.session.execute(
                text(
                    """
                    SELECT m.product_id,
                           sum(abs(m.quantity)) AS qty,
                           sum(abs(m.quantity) * l.unit_price) AS revenue
                    FROM inventory_movements m
                    JOIN sales_order_lines l
                      ON l.sales_order_id = m.source_id AND l.product_id = m.product_id
                    JOIN products p ON p.id = m.product_id
                    WHERE m.source_type = 'sales_order'
                      AND m.reason = 'consume'
                      AND p.product_type = 'purchased'
                      AND m.created_at >= :start
                    GROUP BY m.product_id
                    """
                ),
                {"start": start},
            )
        ).mappings().all()
        averages = {
            row["product_id"]: _money(row["avg_price"])
            for row in (
                await self.session.execute(
                    text(
                        """
                        SELECT l.product_id,
                               sum(l.quantity * l.unit_price) / nullif(sum(l.quantity), 0) AS avg_price
                        FROM purchase_order_lines l
                        JOIN purchase_orders o ON o.id = l.purchase_order_id
                        WHERE o.stock_received AND l.product_id IS NOT NULL
                        GROUP BY l.product_id
                        """
                    )
                )
            ).mappings()
        }
        fallback = {
            row["id"]: row["last_purchase_price"]
            for row in (
                await self.session.execute(
                    text("SELECT id, last_purchase_price FROM products WHERE product_type = 'purchased'")
                )
            ).mappings()
        }
        revenue = Decimal("0")
        cost = Decimal("0")
        units = Decimal("0")
        missing = 0
        for row in sold:
            qty = _qty(row["qty"])
            units += qty
            revenue += _money(row["revenue"])
            price = averages.get(row["product_id"])
            if price is None:
                raw = fallback.get(row["product_id"])
                price = _money(raw) if raw is not None else None
            if price is None:
                missing += 1
            else:
                cost += _money(qty * price)
        spend = _money(
            (
                await self.session.execute(
                    text(
                        """
                        SELECT coalesce(sum(l.quantity * l.unit_price), 0)
                        FROM purchase_order_lines l
                        JOIN purchase_orders o ON o.id = l.purchase_order_id
                        LEFT JOIN products p ON p.id = l.product_id
                        WHERE o.stock_received
                          AND o.updated_at >= :start
                          AND (l.raw_material_id IS NOT NULL OR p.product_type = 'purchased')
                        """
                    ),
                    {"start": start},
                )
            ).scalar()
        )
        incoming = (
            await self.session.execute(
                text(
                    """
                    SELECT count(DISTINCT o.id) AS orders, coalesce(sum(l.quantity), 0) AS qty
                    FROM purchase_orders o
                    JOIN purchase_order_lines l ON l.purchase_order_id = o.id
                    LEFT JOIN products p ON p.id = l.product_id
                    WHERE NOT o.stock_received
                      AND o.status <> 'cancelled'
                      AND (l.raw_material_id IS NOT NULL OR p.product_type = 'purchased')
                    """
                )
            )
        ).mappings().one()
        money = role_has(role_name, VIEW_FINANCIALS)
        profit = revenue - cost
        margin = (profit / revenue * Decimal("100")).quantize(Decimal("0.1")) if revenue else Decimal("0")
        return {
            "revenue": revenue if money else None,
            "cost": cost if money else None,
            "profit": profit if money else None,
            "margin_pct": margin if money else None,
            "units_sold": units,
            "missing_cost": missing,
            "purchase_spend": spend if money else None,
            "incoming_orders": int(incoming["orders"] or 0),
            "incoming_qty": _qty(incoming["qty"]),
        }


def _period_start(period: str) -> datetime:
    if period != "month":
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    now = datetime.now(_IST)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc)


async def role_name_for(session: AsyncSession, actor: User) -> str:
    from app.api.routes.user.user_model import Role

    role = await session.get(Role, actor.role_id)
    return role.role_name if role else ""
