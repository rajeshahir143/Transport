"""ReportLab PDF generators for Builty (Lorry Receipt) and Bill (Material).
Layout inspired by typical Gujarati transporter stationery (SWASTIK style):
header strip, two columns for consignor/consignee, truck/goods details grid,
freight breakup with GST, signature footer.
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)

ACCENT = colors.HexColor("#B22222")  # firebrick — classic transporter stationery
INK = colors.HexColor("#1a1a1a")
LINE = colors.HexColor("#888888")

STYLES = getSampleStyleSheet()
TITLE = ParagraphStyle(
    "t", parent=STYLES["Title"], fontName="Helvetica-Bold",
    fontSize=20, textColor=ACCENT, alignment=1, spaceAfter=2,
)
SUB = ParagraphStyle(
    "s", parent=STYLES["Normal"], fontName="Helvetica",
    fontSize=9, alignment=1, textColor=INK,
)
CELL = ParagraphStyle("c", parent=STYLES["Normal"], fontSize=9, textColor=INK)
BOLD = ParagraphStyle(
    "b", parent=STYLES["Normal"], fontName="Helvetica-Bold",
    fontSize=9, textColor=INK,
)


def _header(firm_name, firm_sub, copy_label):
    data = [[
        Paragraph(firm_name, TITLE),
    ], [
        Paragraph(firm_sub, SUB),
    ], [
        Paragraph(f"<b>{copy_label}</b>", SUB),
    ]]
    t = Table(data, colWidths=[180 * mm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.1, ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def _kv_row(pairs, col_widths):
    cells = []
    for label, value in pairs:
        cells.append(Paragraph(f"<b>{label}</b>", CELL))
        cells.append(Paragraph(str(value or "-"), CELL))
    tbl = Table([cells], colWidths=col_widths)
    tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl


def _party_block(title, lines):
    body = "<br/>".join([f"<b>{title}</b>"] + [str(x) for x in lines if x])
    p = Paragraph(body, CELL)
    tbl = Table([[p]], colWidths=[90 * mm], rowHeights=[32 * mm])
    tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tbl


def generate_builty_pdf(out_path, firm, builty, do_row, copy_label="CONSIGNOR COPY"):
    """firm: dict(name, address, gstin, phone)
       builty: dict row from builtys table (+freight columns)
       do_row: dict row from dos table
    """
    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    story = []
    story.append(_header(
        firm.get("name", "RADHE RADHE DEVELOPER"),
        f"{firm.get('address','')} &nbsp;|&nbsp; GSTIN: {firm.get('gstin','')} &nbsp;|&nbsp; Phone: {firm.get('phone','')}",
        copy_label,
    ))
    story.append(Spacer(1, 4))

    # LR / Builty top row
    story.append(_kv_row([
        ("Builty / LR No", builty.get("builty_no", "")),
        ("Date", builty.get("date", "")),
        ("Truck No", builty.get("truck_no", "")),
    ], col_widths=[28 * mm, 32 * mm, 22 * mm, 28 * mm, 22 * mm, 28 * mm]))
    story.append(Spacer(1, 4))

    # Consignor / Consignee
    consignor_lines = [
        builty.get("consignor") or firm.get("name", ""),
        firm.get("address", ""),
        f"GSTIN: {firm.get('gstin','')}",
    ]
    consignee_lines = [
        builty.get("consignee") or do_row.get("customer_name", ""),
        do_row.get("ship_to") or do_row.get("bill_to") or "",
        f"GSTIN: {do_row.get('customer_gstin','')}",
    ]
    pc_tbl = Table(
        [[_party_block("CONSIGNOR", consignor_lines),
          _party_block("CONSIGNEE", consignee_lines)]],
        colWidths=[90 * mm, 90 * mm],
    )
    pc_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(pc_tbl)
    story.append(Spacer(1, 4))

    # From / To / Material grid
    story.append(_kv_row([
        ("From", builty.get("from_place") or do_row.get("from_place", "")),
        ("To", builty.get("to_place") or do_row.get("to_place", "")),
        ("DO No", do_row.get("do_no", "")),
    ], col_widths=[18 * mm, 50 * mm, 14 * mm, 50 * mm, 18 * mm, 30 * mm]))
    story.append(Spacer(1, 2))
    story.append(_kv_row([
        ("Material", do_row.get("material", "")),
        ("HSN", do_row.get("hsn", "")),
    ], col_widths=[22 * mm, 108 * mm, 14 * mm, 36 * mm]))
    story.append(Spacer(1, 2))
    story.append(_kv_row([
        ("E-Way Bill", builty.get("ewaybill", "")),
        ("Driver", builty.get("driver_name", "")),
    ], col_widths=[22 * mm, 68 * mm, 20 * mm, 70 * mm]))
    story.append(Spacer(1, 6))

    # Freight breakup
    qty = float(builty.get("qty") or 0)
    rate = float(builty.get("freight_rate") or 0)
    freight = float(builty.get("freight_amount") or (qty * rate))
    gst = round(freight * 0.05, 2)  # 5% RCM assumed, informational
    total = round(freight + gst, 2)
    freight_tbl = Table([
        [Paragraph("<b>Particulars</b>", BOLD),
         Paragraph("<b>Qty (TON)</b>", BOLD),
         Paragraph("<b>Rate / TON</b>", BOLD),
         Paragraph("<b>Freight</b>", BOLD)],
        [Paragraph(do_row.get("material", "-"), CELL),
         f"{qty:.3f}", f"{rate:.2f}", f"{freight:.2f}"],
        [Paragraph("GST @ 5% (RCM — payable by consignee)", CELL), "", "", f"{gst:.2f}"],
        [Paragraph("<b>Total Freight</b>", BOLD), "", "", Paragraph(f"<b>{total:.2f}</b>", BOLD)],
    ], colWidths=[90 * mm, 30 * mm, 30 * mm, 30 * mm])
    freight_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3E8E8")),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(freight_tbl)
    story.append(Spacer(1, 6))

    if builty.get("remarks"):
        story.append(Paragraph(f"<b>Remarks:</b> {builty['remarks']}", CELL))
        story.append(Spacer(1, 6))

    # Terms + signatures
    terms = (
        "Terms &amp; Conditions: Goods carried entirely at owner's risk. "
        "Delivery subject to the standard conditions of carriage. "
        "Any claim must be lodged within 7 days of delivery."
    )
    story.append(Paragraph(terms, ParagraphStyle("tx", parent=CELL, fontSize=7.5, textColor=colors.grey)))
    story.append(Spacer(1, 18))

    sig = Table([
        ["Receiver's Signature", "", "For " + firm.get("name", "RADHE RADHE DEVELOPER")],
        ["", "", ""],
        ["", "", "Authorised Signatory"],
    ], colWidths=[70 * mm, 40 * mm, 70 * mm])
    sig.setStyle(TableStyle([
        ("LINEABOVE", (0, 2), (0, 2), 0.5, INK),
        ("LINEABOVE", (2, 2), (2, 2), 0.5, INK),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
    ]))
    story.append(sig)

    doc.build(story)
    return str(out_path)


def generate_bill_pdf(out_path, firm, bill, builties):
    """firm as above; bill: dict row from bills; builties: list of dict rows."""
    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    story = []
    bill_type = bill.get("bill_type", "MATERIAL").upper()
    label = "TAX INVOICE — MATERIAL" if bill_type == "MATERIAL" else "DEBIT NOTE — FREIGHT"
    story.append(_header(
        firm.get("name", "RADHE RADHE DEVELOPER"),
        f"{firm.get('address','')} &nbsp;|&nbsp; GSTIN: {firm.get('gstin','')} &nbsp;|&nbsp; Phone: {firm.get('phone','')}",
        label,
    ))
    story.append(Spacer(1, 4))
    story.append(_kv_row([
        ("Bill No", bill.get("bill_no", "")),
        ("Date", bill.get("bill_date", "")),
        ("Customer", bill.get("customer_name", "")),
    ], col_widths=[20 * mm, 30 * mm, 16 * mm, 30 * mm, 26 * mm, 58 * mm]))
    story.append(Spacer(1, 4))

    # Items table (one line per builty)
    header = [
        Paragraph("<b>#</b>", BOLD),
        Paragraph("<b>Builty No</b>", BOLD),
        Paragraph("<b>Date</b>", BOLD),
        Paragraph("<b>Truck</b>", BOLD),
        Paragraph("<b>DO No</b>", BOLD),
        Paragraph("<b>Qty (TON)</b>", BOLD),
    ]
    rows = [header]
    for i, b in enumerate(builties, 1):
        rows.append([
            str(i),
            b.get("builty_no", ""),
            b.get("date", ""),
            b.get("truck_no", ""),
            b.get("do_no", ""),
            f"{float(b.get('qty') or 0):.3f}",
        ])
    item_tbl = Table(rows, colWidths=[10 * mm, 28 * mm, 24 * mm, 28 * mm, 32 * mm, 28 * mm])
    item_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3E8E8")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
    ]))
    story.append(item_tbl)
    story.append(Spacer(1, 6))

    # Totals
    qty = float(bill.get("total_qty") or 0)
    rate = float(bill.get("rate_per_ton") or 0)
    sub = float(bill.get("subtotal") or (qty * rate))
    cgst = float(bill.get("cgst") or 0)
    sgst = float(bill.get("sgst") or 0)
    igst = float(bill.get("igst") or 0)
    total = float(bill.get("total") or (sub + cgst + sgst + igst))
    totals = Table([
        ["Total Qty", f"{qty:.3f} TON"],
        ["Rate / TON", f"{rate:.2f}"],
        ["Subtotal", f"{sub:.2f}"],
        ["CGST", f"{cgst:.2f}"],
        ["SGST", f"{sgst:.2f}"],
        ["IGST", f"{igst:.2f}"],
        [Paragraph("<b>Grand Total</b>", BOLD), Paragraph(f"<b>{total:.2f}</b>", BOLD)],
    ], colWidths=[60 * mm, 40 * mm], hAlign="RIGHT")
    totals.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
        ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F3E8E8")),
    ]))
    story.append(totals)
    story.append(Spacer(1, 18))

    sig = Table([
        ["Receiver's Signature", "", "For " + firm.get("name", "RADHE RADHE DEVELOPER")],
        ["", "", ""],
        ["", "", "Authorised Signatory"],
    ], colWidths=[70 * mm, 40 * mm, 70 * mm])
    sig.setStyle(TableStyle([
        ("LINEABOVE", (0, 2), (0, 2), 0.5, INK),
        ("LINEABOVE", (2, 2), (2, 2), 0.5, INK),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
    ]))
    story.append(sig)

    doc.build(story)
    return str(out_path)
