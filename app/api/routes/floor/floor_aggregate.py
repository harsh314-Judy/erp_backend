"""Pure totals for the floor logbook.

Department figures count a shared batch once. A worker's figures credit that
same batch in full. Kilograms and pieces are never added together.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal


class FloorFact:
    def __init__(
        self,
        *,
        entry_id: str,
        operation_id: str,
        entry_date: date,
        output_name: str,
        output_unit: str,
        output_quantity: Decimal,
        scrap_quantity: Decimal,
        scrap_unit: str | None,
        input_quantity: Decimal | None,
        input_unit: str | None,
        worker_ids: tuple[str, ...],
    ) -> None:
        self.entry_id = entry_id
        self.operation_id = operation_id
        self.entry_date = entry_date
        self.output_name = output_name
        self.output_unit = output_unit
        self.output_quantity = output_quantity
        self.scrap_quantity = scrap_quantity
        self.scrap_unit = scrap_unit or None
        self.input_quantity = input_quantity
        self.input_unit = input_unit or None
        self.worker_ids = worker_ids


def _add(bucket: dict[str, Decimal], unit: str | None, quantity: Decimal | None) -> None:
    if not unit or quantity is None:
        return
    amount = Decimal(quantity)
    if amount == 0:
        return
    bucket[unit] = bucket.get(unit, Decimal("0")) + amount


def _rates(output: dict[str, Decimal], matched_scrap: dict[str, Decimal]) -> dict[str, Decimal | None]:
    rates: dict[str, Decimal | None] = {}
    for unit, made in output.items():
        scrap = matched_scrap.get(unit)
        if scrap is None or made <= 0:
            rates[unit] = None
            continue
        rates[unit] = (scrap / made * Decimal("100")).quantize(Decimal("0.01"))
    return rates


class Rollup:
    def __init__(self) -> None:
        self.output: dict[str, Decimal] = {}
        self.used: dict[str, Decimal] = {}
        self.scrap: dict[str, Decimal] = {}
        self.matched_scrap: dict[str, Decimal] = {}
        self.entries = 0
        self.shared_entries = 0
        self.active_days: set[date] = set()

    def absorb(self, fact: FloorFact) -> None:
        self.entries += 1
        if len(fact.worker_ids) > 1:
            self.shared_entries += 1
        self.active_days.add(fact.entry_date)
        _add(self.output, fact.output_unit, fact.output_quantity)
        _add(self.used, fact.input_unit, fact.input_quantity)
        scrap_unit = fact.scrap_unit or fact.output_unit
        _add(self.scrap, scrap_unit, fact.scrap_quantity)
        if scrap_unit == fact.output_unit:
            _add(self.matched_scrap, fact.output_unit, fact.scrap_quantity)

    @property
    def scrap_pct(self) -> dict[str, Decimal | None]:
        return _rates(self.output, self.matched_scrap)


def department_rollup(facts: list[FloorFact]) -> Rollup:
    rolled = Rollup()
    for fact in facts:
        rolled.absorb(fact)
    return rolled


def worker_rollup(facts: list[FloorFact], worker_id: str) -> Rollup:
    rolled = Rollup()
    for fact in facts:
        if worker_id in fact.worker_ids:
            rolled.absorb(fact)
    return rolled


def people_rollup(facts: list[FloorFact]) -> dict[str, Rollup]:
    by_worker: dict[str, Rollup] = defaultdict(Rollup)
    for fact in facts:
        seen: set[str] = set()
        for worker_id in fact.worker_ids:
            if worker_id in seen:
                continue
            seen.add(worker_id)
            by_worker[worker_id].absorb(fact)
    return dict(by_worker)


def department_average(facts: list[FloorFact], operation_id: str) -> dict[str, Decimal]:
    """Output per worker-day in one department. A shared batch still counts once per person."""

    totals: dict[str, Decimal] = {}
    days: dict[str, set[tuple[str, date]]] = defaultdict(set)
    for fact in facts:
        if fact.operation_id != operation_id or fact.output_quantity == 0:
            continue
        people = fact.worker_ids or ("",)
        _add(totals, fact.output_unit, fact.output_quantity * len(set(people)))
        for worker_id in set(people):
            days[fact.output_unit].add((worker_id, fact.entry_date))
    return {
        unit: (totals[unit] / Decimal(len(days[unit]))).quantize(Decimal("0.001"))
        for unit in totals
        if days[unit]
    }


def daily_series(facts: list[FloorFact], worker_id: str) -> list[dict]:
    rows: dict[tuple[date, str], dict] = {}
    for fact in facts:
        if worker_id not in fact.worker_ids:
            continue
        key = (fact.entry_date, fact.output_unit)
        row = rows.setdefault(
            key,
            {"date": fact.entry_date, "unit": fact.output_unit, "output": Decimal("0"), "scrap": Decimal("0"), "entries": 0},
        )
        row["output"] += fact.output_quantity
        row["entries"] += 1
        scrap_unit = fact.scrap_unit or fact.output_unit
        if scrap_unit == fact.output_unit:
            row["scrap"] += fact.scrap_quantity
        elif fact.scrap_quantity:
            other = rows.setdefault(
                (fact.entry_date, scrap_unit),
                {"date": fact.entry_date, "unit": scrap_unit, "output": Decimal("0"), "scrap": Decimal("0"), "entries": 0},
            )
            other["scrap"] += fact.scrap_quantity
    return [rows[key] for key in sorted(rows)]


def item_breakdown(facts: list[FloorFact], worker_id: str) -> list[dict]:
    rows: dict[tuple[str, str], dict] = {}
    for fact in facts:
        if worker_id not in fact.worker_ids:
            continue
        key = (fact.output_name, fact.output_unit)
        row = rows.setdefault(
            key,
            {"name": fact.output_name, "unit": fact.output_unit, "output": Decimal("0"), "scrap": Decimal("0"), "entries": 0},
        )
        row["output"] += fact.output_quantity
        row["entries"] += 1
        scrap_unit = fact.scrap_unit or fact.output_unit
        if scrap_unit == fact.output_unit:
            row["scrap"] += fact.scrap_quantity
    return sorted(rows.values(), key=lambda item: (-item["output"], item["name"]))
