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
    risk = Table([[P("AT OWNER'S RISK")]], colWidths=[198 * mm])
    risk.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.65,colors.black),
                              ("LEFTPADDING",(0,0),(-1,-1),4),
                              ("TOPPADDING",(0,0),(-1,-1),1),
                              ("BOTTOMPADDING",(0,0),(-1,-1),1)]))
    story.append(risk)
    head = Table([[P(val(FIRM if "FIRM" in globals() else firm, "name", "MANSI COAL CARRIER").upper(), title)],
                  [P("LIGNITE SUPPLIER & COMMISSION AGENT", subtitle)]],
                 colWidths=[198 * mm], rowHeights=[23 * mm, 12 * mm])
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
    story.append(cell_table(row1, [24*mm, 76*mm, 24*mm, 74*mm]))

    # Consignor / consignee columns
    consignor_name = val(builty, "consignor", "G.M.D.C. LTD.")
    consignor_gstin = val(do_row, "gmdc_gstin", "24AAACG7987P1ZT")
    consignee_name = val(builty, "consignee", val(do_row, "customer_name", ""))
    destination = val(builty, "center_name", val(builty, "to_place", val(do_row, "to_place", "")))
    consignee_gstin = val(do_row, "customer_gstin", "")
    left_lines = [P(": CONSIGNOR :", bold), P(consignor_name), P(""), P("GSTIN : " + str(consignor_gstin))]
    right_lines = [P(": CONSIGNEE :", bold), P(consignee_name), P(destination), P("GSTIN : " + str(consignee_gstin))]
    parties = Table([[left_lines, right_lines]], colWidths=[99*mm, 99*mm])
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
    story.append(cell_table(row2, [19*mm, 27*mm, 21*mm, 27*mm, 24*mm, 25*mm, 22*mm, 33*mm]))

    desc = val(do_row, "material", val(do_row, "item_name", "LIGNITE"))
    to_place = val(builty, "center_name", val(builty, "to_place", val(do_row, "to_place", "")))
    if to_place:
        desc = (str(desc) + "    " + str(to_place)).strip()
    # Sample layout: Description / Weight / Freight / To Pay / Paid Amount
    goods = Table([
        [P("D e s c r i p t i o n", bold), P("Weight", bold), P("Freight", bold), Paragraph("To Pay /<br/>Paid Amount", bold)],
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
    # Escape user/PDF-derived values individually, but keep ReportLab <br/> tags as real line breaks.
    truck_details = Paragraph(
        "Truck No. : " + _safe(truck, 80) +
        "<br/>Driver's Name : " + _safe(driver, 100) +
        "<br/>Address : " + _safe(address, 160) +
        "<br/>Truck Owner Name : " + _safe(owner, 100) +
        "<br/>Mobile No. : " + _safe(mobile, 40),
        small,
    )
    gst_labels = Paragraph(
        f"CGST {cgst_rate:.2f}%<br/>SGST {sgst_rate:.2f}%<br/>Total :",
        small,
    )
    gst_values = Paragraph(
        f"{freight * cgst_rate / 100:.2f}<br/>"
        f"{freight * sgst_rate / 100:.2f}<br/>"
        f"{freight * (cgst_rate + sgst_rate) / 100:.2f}",
        right,
    )
    gst_rows = [[truck_details, gst_labels, gst_values]]
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
    """Create a printable final bill PDF with Builty-wise weights, rates and amounts."""
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
        leftMargin=8*mm, rightMargin=8*mm, topMargin=8*mm, bottomMargin=9*mm)
    normal = ParagraphStyle("FinalBillNormal", parent=CELL, fontSize=8.2, leading=10)
    bold = ParagraphStyle("FinalBillBold", parent=normal, fontName="Helvetica-Bold")
    title = ParagraphStyle("FinalBillTitle", parent=normal, fontName="Helvetica-Bold",
                           fontSize=18, leading=22, alignment=1)
    subtitle = ParagraphStyle("FinalBillSubtitle", parent=normal, fontName="Helvetica-Bold",
                             fontSize=11, leading=14, alignment=1)
    center = ParagraphStyle("FinalBillCenter", parent=normal, alignment=1)
    right = ParagraphStyle("FinalBillRight", parent=normal, alignment=2)
    def para(value, style=normal):
        return Paragraph(_safe(str(value if value is not None else ""), 300), style)
    def num(value):
        try: return float(value or 0)
        except (ValueError, TypeError): return 0.0
    def money(value): return f"{num(value):,.2f}"
    def wt(value): return f"{num(value):,.3f}"

    bill_type = str(bill.get("bill_type") or "MATERIAL").upper()
    invoice_label = "FINAL BILL / TAX INVOICE" if bill_type == "MATERIAL" else "DEBIT NOTE — FREIGHT"
    firm_name = firm.get("name") or "MANSI COAL CARRIER"

    # Prevent the entire extracted DO PDF text from appearing in a single invoice cell.
    # The bill should show concise, readable values sourced from the linked Builty rows.
    def clean_detail(value, fallback=""):
        value = str(value or "").strip()
        noisy_markers = ("Whether Tax Payable", "Schedule Date", "Transporter Code",
                         "Transporter Name:", "Qty:", "Extended Price", "Total Order")
        if len(value) > 90 or any(marker.lower() in value.lower() for marker in noisy_markers):
            return str(fallback or "")
        return value

    first = builties[0] if builties else {}
    do_numbers = list(dict.fromkeys(str(x.get("do_no") or "").strip() for x in builties if str(x.get("do_no") or "").strip()))
    detail_do = ", ".join(do_numbers)
    detail_item = first.get("material") or ""
    # Final Bill must show only the GMDC material name, not copied PDF text.
    material_match = __import__("re").search(
        r"\b(MATA\s+NO\s+MADH\s+'?A'?\s+GRADE|BHAVNAGAR\s+'?A'?\s+GRADE)\b",
        str(detail_item), __import__("re").I)
    if material_match:
        detail_item = __import__("re").sub(r"\s+", " ", material_match.group(1)).upper()
        detail_item = __import__("re").sub(r"\bA\s+GRADE\b", "'A' GRADE", detail_item)
    else:
        detail_item = clean_detail(detail_item, "")
    detail_mines = clean_detail(first.get("from_place"), "")
    party = clean_detail(bill.get("customer_name") or bill.get("party_name"), "")
    gstin = clean_detail(bill.get("customer_gstin"), "")
    shown_do = clean_detail(bill.get("do_no"), detail_do) or detail_do
    shown_item = clean_detail(bill.get("item_name"), detail_item) or detail_item
    shown_mines = clean_detail(bill.get("mines_name"), detail_mines) or detail_mines
    story = [
        para(firm_name.upper(), title),
        para("LIGNITE SUPPLIER & COMMISSION AGENT", subtitle),
        Spacer(1, 5),
    ]
    details = Table([
        [para("Bill No. :", bold), para(bill.get("bill_no") or "", bold),
         para("Invoice Date :", bold), para(bill.get("bill_date") or "", bold),
         para("Due Date :", bold), para(bill.get("due_date") or "", bold)],
        [para("Party Name :", bold), para(party),
         para("Customer GSTIN :", bold), para(gstin),
         para("GST Paid By :", bold), para(bill.get("gst_paid_by") or "")],
        [para("DO No. :", bold), para(shown_do),
         para("Item Name :", bold), para(shown_item),
         para("Mines Name :", bold), para(shown_mines)],
        [para("Invoice Type :", bold), para(invoice_label, bold),
         para("Period From :", bold), para(bill.get("period_from") or ""),
         para("Period To :", bold), para(bill.get("period_to") or "")],
    ], colWidths=[20*mm, 43*mm, 22*mm, 43*mm, 22*mm, 36*mm])
    details.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.6,LINE), ("INNERGRID",(0,0),(-1,-1),0.3,LINE),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("LEFTPADDING",(0,0),(-1,-1),3),
        ("RIGHTPADDING",(0,0),(-1,-1),3), ("TOPPADDING",(0,0),(-1,-1),6),
        ("BOTTOMPADDING",(0,0),(-1,-1),6),
    ]))
    story.extend([details, Spacer(1, 8)])

    headings = ["#", "Date", "Builty No.", "DO No.", "Vehicle No.",
                "Mines", "Desp. Wt.", "Rcpt. Wt.", "Rate Rs.", "Amount Rs."]
    rows = [[para(h, bold) for h in headings]]
    total_desp = total_rcpt = total_amount = 0.0
    for i, item in enumerate(builties, 1):
        desp = num(item.get("despatch_weight") or item.get("qty"))
        rcpt = num(item.get("receipt_weight") or item.get("qty"))
        rate = num(item.get("sale_rate") or item.get("rate_per_ton"))
        basis = str(bill.get("weight_basis") or "Both Less")
        bill_rate = num(bill.get("rate_per_ton")) or rate
        if basis == "Despatch":
            bill_weight = desp
        elif basis == "Receipt":
            bill_weight = rcpt
        else:
            bill_weight = rcpt - desp
        amount = bill_weight * bill_rate
        total_desp += desp
        total_rcpt += rcpt
        total_amount += amount
        rows.append([
            para(i, center), para(item.get("date") or "", center),
            para(item.get("builty_no") or "", center), para(item.get("do_no") or "", center),
            para(item.get("truck_no") or "", center), para(item.get("from_place") or "", center),
            para(wt(desp), right), para(wt(rcpt), right), para(money(rate), right),
            para(money(amount), right),
        ])
    rows.append([
        para("", bold), para("", bold), para("TOTAL", bold), para("", bold), para("", bold),
        para("", bold), para(wt(total_desp), bold), para(wt(total_rcpt), bold),
        para("", bold), para(money(total_amount), bold),
    ])
    widths = [7*mm, 17*mm, 22*mm, 21*mm, 25*mm, 19*mm, 19*mm, 19*mm, 19*mm, 23*mm]
    item_tbl = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    item_tbl.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.6,LINE), ("INNERGRID",(0,0),(-1,-1),0.3,LINE),
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#EAEAEA")),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#F3E8E8")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("LEFTPADDING",(0,0),(-1,-1),2),
        ("RIGHTPADDING",(0,0),(-1,-1),2), ("TOPPADDING",(0,0),(-1,-1),4),
        ("BOTTOMPADDING",(0,0),(-1,-1),4),
    ]))
    story.extend([item_tbl, Spacer(1, 6)])

    qty = num(bill.get("total_qty"))
    rate = num(bill.get("rate_per_ton"))
    subtotal = num(bill.get("subtotal")) or qty * rate
    cgst, sgst, igst = num(bill.get("cgst")), num(bill.get("sgst")), num(bill.get("igst"))
    round_off = num(bill.get("round_off"))
    total = num(bill.get("total")) or subtotal + cgst + sgst + igst + round_off
    totals = Table([
        [para("No. of Builties", bold), para(len(builties), right),
         para("Despatch Weight", bold), para(wt(total_desp), right),
         para("Receipt Weight", bold), para(wt(total_rcpt), right)],
        [para("Bill Weight (TON)", bold), para(wt(qty), right),
         para("Rate / TON", bold), para(money(rate), right),
         para("Gross Amount Rs.", bold), para(money(subtotal), right)],
        [para("CGST Rs.", bold), para(money(cgst), right),
         para("SGST Rs.", bold), para(money(sgst), right),
         para("IGST Rs.", bold), para(money(igst), right)],
        [para("Round Off Rs.", bold), para(money(round_off), right),
         para("Remarks", bold), para(bill.get("remarks") or "", normal),
         para("NET AMOUNT Rs.", bold), para(money(total), bold)],
    ], colWidths=[27*mm, 25*mm, 27*mm, 25*mm, 28*mm, 39*mm])
    totals.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.6,LINE), ("INNERGRID",(0,0),(-1,-1),0.3,LINE),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("LEFTPADDING",(0,0),(-1,-1),3),
        ("RIGHTPADDING",(0,0),(-1,-1),3), ("TOPPADDING",(0,0),(-1,-1),5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5), ("BACKGROUND",(4,3),(5,3),colors.HexColor("#F3E8E8")),
    ]))
    story.extend([totals, Spacer(1, 18)])
    sig = Table([
        [para("Receiver's Signature"), "", para("For " + firm_name, bold)],
        ["", "", ""],
        ["", "", para("Authorised Signatory", bold)],
    ], colWidths=[60*mm, 50*mm, 60*mm])
    sig.setStyle(TableStyle([
        ("LINEABOVE",(0,2),(0,2),0.5,INK), ("LINEABOVE",(2,2),(2,2),0.5,INK),
        ("ALIGN",(2,0),(2,-1),"RIGHT"), ("TOPPADDING",(0,0),(-1,-1),4),
    ]))
    story.append(sig)
    doc.build(story)
    return str(out_path)
