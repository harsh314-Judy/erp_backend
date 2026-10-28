"""Tally-style GST invoice PDF.

The seller name is taken from the sample bill (SDS27). That bill does not
print a GSTIN, so the number comes from company settings.
"""

from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SELLER_NAME = "SDS27"

_ONES = [
    "",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
_FONTS: tuple[str, str, str] | None = None


@dataclass(frozen=True)
class BillLine:
    description: str
    quantity: Decimal
    rate: Decimal
    unit: str
    gst_percent: Decimal
    amount: Decimal


@dataclass(frozen=True)
class Bill:
    number: str
    dated: str
    buyer_name: str
    buyer_address: str
    buyer_state: str
    buyer_gstin: str
    buyer_phone: str
    order_ref: str
    notes: str
    lines: list[BillLine]
    taxable: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    delivery: Decimal
    total: Decimal
    same_state: bool
    previous_balance: Decimal
    current_balance: Decimal
    seller_gstin: str
    seller_address: str
    seller_state: str


def render_invoice_pdf(bill: Bill) -> bytes:
    regular, bold, rupee = _fonts()
    styles = _styles(regular, bold)
    story: list = []
    for index, label in enumerate(("Original", "Duplicate")):
        if index:
            story.append(PageBreak())
        story.extend(_copy(bill, label, styles, rupee, regular, bold))
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=f"Invoice {bill.number}",
        author=SELLER_NAME,
    )
    document.build(story)
    return buffer.getvalue()


def rupees_in_words(amount: Decimal) -> str:
    quantized = amount.quantize(Decimal("0.01"))
    rupees = int(quantized)
    paise = int((quantized - rupees) * 100)
    words = f"INR {_indian(rupees)}"
    if paise:
        words += f" and {_indian(paise)} Paise"
    return f"{words} Only"


def inr(amount: Decimal, rupee: str = "Rs.") -> str:
    sign = "-" if amount < 0 else ""
    whole, frac = f"{abs(amount):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups: list[str] = []
        while head:
            groups.append(head[-2:])
            head = head[:-2]
        whole = ",".join(reversed(groups)) + "," + tail
    return f"{sign}{rupee} {whole}.{frac}"


def _copy(bill: Bill, label: str, styles: dict[str, ParagraphStyle], rupee: str, regular: str, bold: str) -> list:
    story: list = [
        Paragraph(f"INVOICE <font size='9'>({label})</font>", styles["title"]),
        Paragraph(SELLER_NAME, styles["seller"]),
        Paragraph(f"GSTIN: {_dash(bill.seller_gstin)}", styles["center"]),
    ]
    address = ", ".join(part for part in (bill.seller_address.strip(), bill.seller_state.strip()) if part)
    if address:
        story.append(Paragraph(_esc(address), styles["center"]))
    story.append(Spacer(1, 3 * mm))

    buyer = "<br/>".join(
        [
            "<b>Buyer (Bill to)</b>",
            f"<b>{_esc(bill.buyer_name)}</b>",
            _esc(bill.buyer_address),
            _esc(bill.buyer_state),
            f"GSTIN: {_esc(_dash(bill.buyer_gstin))}",
            f"Phone: {_esc(_dash(bill.buyer_phone))}",
        ]
    )
    meta = Table(
        [
            [_p("Invoice No.", styles["label"]), _p(bill.number, styles["value"])],
            [_p("Dated", styles["label"]), _p(bill.dated, styles["value"])],
            [_p("Buyer's Order No.", styles["label"]), _p(bill.order_ref, styles["value"])],
            [_p("Other References", styles["label"]), _p(_dash(bill.notes), styles["value"])],
        ],
        colWidths=[28 * mm, 44 * mm],
    )
    meta.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LINEBELOW", (0, 0), (-1, -2), 0.2, colors.HexColor("#cccccc")),
            ]
        )
    )
    header = Table(
        [[Paragraph(buyer, styles["body"]), meta]],
        colWidths=[106 * mm, 80 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.black),
                ("LINEAFTER", (0, 0), (0, 0), 0.4, colors.black),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 3 * mm))

    rows = [[
        _p("Sl", styles["head"]),
        _p("Description of Goods", styles["head"]),
        _p("Quantity", styles["head_right"]),
        _p("Rate", styles["head_right"]),
        _p("per", styles["head"]),
        _p("GST %", styles["head_right"]),
        _p("Amount", styles["head_right"]),
    ]]
    for index, line in enumerate(bill.lines, start=1):
        rows.append([
            _p(str(index), styles["cell"]),
            _p(_esc(line.description), styles["cell"]),
            _p(_qty(line.quantity), styles["right"]),
            _p(f"{line.rate:.2f}", styles["right"]),
            _p(_esc(line.unit or "Nos"), styles["cell"]),
            _p(_qty(line.gst_percent), styles["right"]),
            _p(f"{line.amount:.2f}", styles["right"]),
        ])
    rows.append([
        "",
        _p("Total", styles["head"]),
        "",
        "",
        "",
        "",
        _p(f"{bill.taxable:.2f}", styles["head_right"]),
    ])
    table = Table(rows, colWidths=[10 * mm, 72 * mm, 24 * mm, 22 * mm, 16 * mm, 16 * mm, 26 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), bold),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                ("GRID", (0, 0), (-1, -2), 0.3, colors.black),
                ("BOX", (0, -1), (-1, -1), 0.4, colors.black),
                ("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("FONTNAME", (0, 0), (-1, -1), regular),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 2 * mm))

    tax_rows = [[_p("Taxable value", styles["label"]), _p(inr(bill.taxable, rupee), styles["right"])]]
    if bill.same_state:
        tax_rows.append([_p("CGST", styles["label"]), _p(inr(bill.cgst, rupee), styles["right"])])
        tax_rows.append([_p("SGST", styles["label"]), _p(inr(bill.sgst, rupee), styles["right"])])
    else:
        tax_rows.append([_p("IGST", styles["label"]), _p(inr(bill.igst, rupee), styles["right"])])
    if bill.delivery:
        tax_rows.append([_p("Delivery charge", styles["label"]), _p(inr(bill.delivery, rupee), styles["right"])])
    tax_rows.append([_p("Grand total", styles["head"]), _p(inr(bill.total, rupee), styles["head_right"])])
    tax = Table(tax_rows, colWidths=[40 * mm, 40 * mm], hAlign="RIGHT")
    tax.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("FONTNAME", (0, 0), (-1, -1), regular),
            ]
        )
    )
    story.append(tax)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("<b>Amount Chargeable (in words)</b>", styles["label"]))
    story.append(Paragraph(_esc(rupees_in_words(bill.total)), styles["body"]))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("<b>Declaration</b>", styles["label"]))
    story.append(Paragraph(
        "We declare that this invoice shows the actual price of the goods described "
        "and that all particulars are true and correct.",
        styles["small"],
    ))
    story.append(Paragraph("E. &amp; O.E", styles["small"]))
    story.append(Spacer(1, 4 * mm))

    balance = Table(
        [
            [_p("Previous Balance", styles["label"]), _p(f"{inr(bill.previous_balance, rupee)} Dr", styles["right"])],
            [_p("Current Balance", styles["label"]), _p(f"{inr(bill.current_balance, rupee)} Dr", styles["right"])],
        ],
        colWidths=[40 * mm, 50 * mm],
    )
    sign = [
        Paragraph(f"for <b>{SELLER_NAME}</b>", styles["right"]),
        Spacer(1, 8 * mm),
        Paragraph("Authorised Signatory", styles["right"]),
    ]
    footer = Table([[balance, sign]], colWidths=[106 * mm, 80 * mm])
    footer.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    story.append(footer)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("This is a Computer Generated Invoice", styles["center"]))
    return story


def _styles(regular: str, bold: str) -> dict[str, ParagraphStyle]:
    def make(name: str, font: str, size: int, align: int = 0, leading: int = 10) -> ParagraphStyle:
        return ParagraphStyle(
            name,
            fontName=font,
            fontSize=size,
            alignment=align,
            leading=leading,
            textColor=colors.black,
        )

    return {
        "title": make("title", bold, 12, TA_CENTER, 14),
        "seller": make("seller", bold, 16, TA_CENTER, 18),
        "center": make("center", regular, 8, TA_CENTER, 10),
        "body": make("body", regular, 8, leading=11),
        "small": make("small", regular, 8),
        "label": make("label", bold, 8),
        "value": make("value", regular, 8),
        "head": make("head", bold, 8),
        "head_right": make("head_right", bold, 8, TA_RIGHT),
        "cell": make("cell", regular, 8),
        "right": make("right", regular, 8, TA_RIGHT),
    }


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def _esc(value: str) -> str:
    return (value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")


def _dash(value: str) -> str:
    text = (value or "").strip()
    return text or "—"


def _qty(value: Decimal) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def _indian(value: int) -> str:
    if value == 0:
        return "Zero"
    crore, value = divmod(value, 10_000_000)
    lakh, value = divmod(value, 100_000)
    thousand, rest = divmod(value, 1_000)
    parts: list[str] = []
    if crore:
        parts.append(f"{_upto999(crore)} Crore")
    if lakh:
        parts.append(f"{_upto99(lakh)} Lakh")
    if thousand:
        parts.append(f"{_upto99(thousand)} Thousand")
    if rest:
        parts.append(_upto999(rest))
    return " ".join(parts)


def _upto99(value: int) -> str:
    if value < 20:
        return _ONES[value]
    ten, one = divmod(value, 10)
    if one:
        return f"{_TENS[ten]} {_ONES[one]}"
    return _TENS[ten]


def _upto999(value: int) -> str:
    hundred, rest = divmod(value, 100)
    parts: list[str] = []
    if hundred:
        parts.append(f"{_ONES[hundred]} Hundred")
    if rest:
        parts.append(_upto99(rest))
    return " ".join(parts)


def _fonts() -> tuple[str, str, str]:
    global _FONTS
    if _FONTS is not None:
        return _FONTS
    regular = Path(r"C:\Windows\Fonts\arial.ttf")
    bold = Path(r"C:\Windows\Fonts\arialbd.ttf")
    if regular.exists() and bold.exists():
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        pdfmetrics.registerFont(TTFont("Invoice", str(regular)))
        pdfmetrics.registerFont(TTFont("Invoice-Bold", str(bold)))
        _FONTS = ("Invoice", "Invoice-Bold", "₹")
    else:
        _FONTS = ("Helvetica", "Helvetica-Bold", "Rs.")
    return _FONTS
