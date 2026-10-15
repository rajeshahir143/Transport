"""ReportLab PDF generators for Builty (Lorry Receipt) and Bill (Material).
Layout inspired by typical Gujarati transporter stationery (SWASTIK style):
header strip, two columns for consignor/consignee, truck/goods details grid,
freight breakup with GST, signature footer.
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from xml.sax.saxutils import escape
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
CELL = ParagraphStyle("c", parent=STYLES["Normal"], fontSize=8, leading=10, textColor=INK, wordWrap="CJK", splitLongWords=1)
BOLD = ParagraphStyle(
    "b", parent=STYLES["Normal"], fontName="Helvetica-Bold",
    fontSize=9, textColor=INK,
)


def _safe(value, limit=500):
    """Escape user/PDF text before passing it to ReportLab Paragraph markup."""
    text = str(value or "").replace("\r", " ").replace("\n", " ")
    return escape(text[:limit])


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
        cells.append(Paragraph(_safe(value or "-"), CELL))
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
    body = "<br/>".join([f"<b>{_safe(title)}</b>"] + [_safe(x, 240) for x in lines if x])
    p = Paragraph(body, CELL)
    tbl = Table([[p]], colWidths=[90 * mm], splitByRow=1)
    tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tbl


def generate_builty_pdf(out_path, firm, builty, do_row, copy_label="CONSIGNOR COPY"):
    """Generate a compact, SWASTIK-style Lorry Receipt matching the supplied sample."""
    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=4 * mm, rightMargin=4 * mm,
        topMargin=3 * mm, bottomMargin=3 * mm,
    )
    small = ParagraphStyle("lrsmall", parent=CELL, fontSize=8, leading=10)
    bold = ParagraphStyle("lrbold", parent=small, fontName="Helvetica-Bold")
    title = ParagraphStyle("lrtitle", parent=STYLES["Title"], fontName="Helvetica-Bold",
                           fontSize=19, leading=21, alignment=1, textColor=colors.black, spaceAfter=0)
    subtitle = ParagraphStyle("lrsub", parent=STYLES["Normal"], fontName="Helvetica-Bold",
                              fontSize=12, leading=14, alignment=1, textColor=colors.black)
    center = ParagraphStyle("lrcenter", parent=small, alignment=1)
    right = ParagraphStyle("lrright", parent=small, alignment=2)
    story = []

    def P(value="", style=small):
        return Paragraph(_safe(value or "", 350), style)

    def cell_table(rows, widths, heights=None, font=small, align=None):
        t = Table(rows, colWidths=widths, rowHeights=heights, repeatRows=0, hAlign="LEFT")
        commands = [
            ("BOX", (0, 0), (-1, -1), 0.65, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        if align:
            commands.extend(align)
        t.setStyle(TableStyle(commands))
        return t

    def val(obj, key, default=""):
        try:
            return obj.get(key) or default
        except Exception:
            return default

    # Top risk note and transporter heading
    risk = Table([[P("AT OWNER'S RISK")]], colWidths=[202 * mm])
    risk.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.65,colors.black),
                              ("LEFTPADDING",(0,0),(-1,-1),4),
                              ("TOPPADDING",(0,0),(-1,-1),1),
                              ("BOTTOMPADDING",(0,0),(-1,-1),1)]))
    story.append(risk)
    head = Table([[P(val(FIRM if "FIRM" in globals() else firm, "name", "MANSI COAL CARRIER").upper(), title)],
                  [P("LIGNITE SUPPLIER & COMMISSION AGENT", subtitle)]],
                 colWidths=[202 * mm], rowHeights=[23 * mm, 12 * mm])
    head.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.65,colors.black),
                              ("LEFTPADDING",(0,0),(-1,-1),3),
                              ("RIGHTPADDING",(0,0),(-1,-1),3),
                              ("TOPPADDING",(0,0),(-1,-1),0),
                              ("BOTTOMPADDING",(0,0),(-1,-1),0),
                              ("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(head)

    lr_no = val(builty, "builty_no", val(builty, "lr_no", val(builty, "id", "")))
    lr_date = val(builty, "date", "")
    row1 = [[P("L.R. No."), P(lr_no, bold), P("L.R. Date"), P(lr_date, bold)]]
    story.append(cell_table(row1, [25*mm, 78*mm, 25*mm, 74*mm]))

    # Consignor / consignee columns
    consignor_name = val(builty, "consignor", "G.M.D.C. LTD.")
    consignor_gstin = val(do_row, "gmdc_gstin", "24AAACG7987P1ZT")
    consignee_name = val(builty, "consignee", val(do_row, "customer_name", ""))
    destination = val(builty, "center_name", val(builty, "to_place", val(do_row, "to_place", "")))
    consignee_gstin = val(do_row, "customer_gstin", "")
    left_lines = [P(": CONSIGNOR :", bold), P(consignor_name), P(""), P("GSTIN : " + str(consignor_gstin))]
    right_lines = [P(": CONSIGNEE :", bold), P(consignee_name), P(destination), P("GSTIN : " + str(consignee_gstin))]
    parties = Table([[left_lines, right_lines]], colWidths=[101*mm, 101*mm])
    parties.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.65,colors.black),("INNERGRID",(0,0),(-1,-1),0.45,colors.black),
        ("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),
        ("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]))
    story.append(parties)

    row2 = [[P("DO No. :"), P(val(do_row, "do_no", val(do_row, "gmdc_do_no", "")), bold),
             P("Regi.No. :"), P(val(do_row, "regi_no", val(do_row, "customer_no", "")), bold),
             P("Challan No. :"), P(val(builty, "challan_no", ""), bold),
             P("Quota Dt. :"), P(val(builty, "quota_date", ""), bold)]]
    story.append(cell_table(row2, [20*mm, 28*mm, 22*mm, 28*mm, 25*mm, 26*mm, 22*mm, 31*mm]))

    desc = val(do_row, "material", val(do_row, "item_name", "LIGNITE"))
    to_place = val(builty, "center_name", val(builty, "to_place", val(do_row, "to_place", "")))
    if to_place:
        desc = (str(desc) + "    " + str(to_place)).strip()
    # Sample layout: Description / Weight / Freight / To Pay / Paid Amount
    goods = Table([
        [P("D e s c r i p t i o n", bold), P("Weight", bold), P("Freight", bold), P("To Pay /<br/>Paid Amount", bold)],
        [P(desc, bold), P(f"{float(val(builty, 'qty', 0) or 0):.3f}", center),
         P(f"{float(val(builty, 'freight_amount', 0) or 0):.2f}" if float(val(builty, 'freight_amount', 0) or 0) else "", center),
         P("To Be Billed", center)]
    ], colWidths=[96*mm, 33*mm, 37*mm, 36*mm], rowHeights=[12*mm, 14*mm])
    goods.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.65,colors.black),("INNERGRID",(0,0),(-1,-1),0.45,colors.black),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
    ]))
    story.append(goods)

    truck = val(builty, "truck_no", "")
    driver = val(builty, "driver_name", "")
    address = val(builty, "address", "")
    mobile = val(builty, "mobile_no", "")
    owner = val(builty, "owner_name", "")
    cgst_rate = float(val(builty, "cgst_rate", 0) or 0)
    sgst_rate = float(val(builty, "sgst_rate", 0) or 0)
    freight = float(val(builty, "freight_amount", 0) or 0)
    gst_rows = [
        [P(f"Truck No. :       {truck}<br/>Driver's Name :    {driver}<br/>Address :          {address}<br/>Truck Owner Name : {owner}<br/>Mobile No. :       {mobile}"),
         P(f"CGST  {cgst_rate:.2f}%<br/>SGST  {sgst_rate:.2f}%<br/>Total :", small),
         P(f"{freight * cgst_rate / 100:.2f}<br/>{freight * sgst_rate / 100:.2f}<br/>{freight * (cgst_rate + sgst_rate) / 100:.2f}", right)]
    ]
    details = Table(gst_rows, colWidths=[126*mm, 42*mm, 34*mm], rowHeights=[29*mm])
    details.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.65,colors.black),("INNERGRID",(0,0),(-1,-1),0.45,colors.black),
        ("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),
        ("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]))
    story.append(details)

    terms_text = "* 200 Kg. Shortage allowed. We are not responsible for quality,\nLignite direct loading from mines.\n* GST TO BE PAID UNDER RCM"
    terms = Table([[P(terms_text), P("For MANSI COAL CARRIER", bold)]],
                  colWidths=[124*mm, 78*mm], rowHeights=[20*mm])
    terms.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.65,colors.black),("INNERGRID",(0,0),(-1,-1),0.45,colors.black),
        ("VALIGN",(0,0),(-1,-1),"BOTTOM"),("LEFTPADDING",(0,0),(-1,-1),5),
        ("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]))
    story.append(terms)
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
