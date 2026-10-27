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
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Flowable,
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

    # Use the currently selected company's name consistently on the Builty.
    firm_name = str(val(firm, "name", "MANSI COAL CARRIER")).strip() or "MANSI COAL CARRIER"
    # Top risk note and company heading
    risk = Table([[P("AT OWNER'S RISK")]], colWidths=[198 * mm])
    risk.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.65,colors.black),
                              ("LEFTPADDING",(0,0),(-1,-1),4),
                              ("TOPPADDING",(0,0),(-1,-1),1),
                              ("BOTTOMPADDING",(0,0),(-1,-1),1)]))
    story.append(risk)
    head = Table([[P(firm_name.upper(), title)],
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
    terms = Table([[P(terms_text), P("For " + firm_name.upper(), bold)]],
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
    """Print compact tax invoice inspired by the user's MANSI COAL CAREER sample."""
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
        leftMargin=9*mm, rightMargin=9*mm, topMargin=8*mm, bottomMargin=8*mm)
    normal = ParagraphStyle("InvoiceNormal", parent=CELL, fontSize=7.2, leading=8.4)
    bold = ParagraphStyle("InvoiceBold", parent=normal, fontName="Helvetica-Bold")
    title = ParagraphStyle("InvoiceTitle", parent=normal, fontName="Helvetica-Bold",
                           fontSize=16, leading=18, alignment=1)
    center = ParagraphStyle("InvoiceCenter", parent=normal, alignment=1)
    right = ParagraphStyle("InvoiceRight", parent=normal, alignment=2)
    def para(v, style=normal): return Paragraph(_safe(v, 260), style)
    def num(v):
        try: return float(v or 0)
        except (TypeError, ValueError): return 0.0
    def money(v): return f"{num(v):,.2f}"
    def wt(v): return f"{num(v):,.3f}"
    firm_name = str(firm.get("name") or "MANSI COAL CAREER").strip().upper()
    bill_type = str(bill.get("bill_type") or "MATERIAL").upper()
    invoice_label = "TAX INVOICE" if bill_type == "MATERIAL" else "DEBIT NOTE - FREIGHT"
    first = builties[0] if builties else {}
    party = bill.get("customer_name") or bill.get("party_name") or first.get("customer_name") or ""
    address = bill.get("customer_address") or first.get("customer_address") or ""
    gstin = bill.get("customer_gstin") or first.get("customer_gstin") or ""
    pan = bill.get("customer_pan") or ""
    mines = bill.get("mines_name") or first.get("from_place") or ""
    material = bill.get("item_name") or first.get("material") or ""
    do_numbers = list(dict.fromkeys(str(x.get("do_no") or "").strip() for x in builties if str(x.get("do_no") or "").strip()))
    do_text = ", ".join(do_numbers)
    bill_no = bill.get("bill_no") or ""
    bill_date = bill.get("bill_date") or ""
    invoice_head = Table([[para("No. : " + str(bill_no), bold), para(invoice_label, title),
        para("Date : " + str(bill_date), bold)]], colWidths=[55*mm, 75*mm, 52*mm], rowHeights=[14*mm])
    invoice_head.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),1.2,colors.black), ("INNERGRID",(0,0),(-1,-1),0.8,colors.black),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("LEFTPADDING",(0,0),(-1,-1),4), ("RIGHTPADDING",(0,0),(-1,-1),4),
    ]))
    display_bill_date = str(bill_date or "")
    try:
        if len(display_bill_date) >= 10 and display_bill_date[4] == "-" and display_bill_date[7] == "-":
            display_bill_date = display_bill_date[8:10] + "/" + display_bill_date[5:7] + "/" + display_bill_date[2:4]
    except (TypeError, ValueError):
        pass
    invoice_title = ParagraphStyle("BillInvoiceTitle", parent=title, fontSize=13, leading=15, alignment=1)
    company_head = Table([
        [para(firm_name, title), ""],
        [para("GSTIN : " + str(firm.get("gstin") or ""), bold),
         para("No. : " + str(bill_no), ParagraphStyle("BillNoRight", parent=bold, alignment=2))],
        [para("TAX INVOICE", invoice_title),
         para("Date : " + display_bill_date, ParagraphStyle("BillDateRight", parent=bold, alignment=2))],
    ], colWidths=[91*mm, 91*mm], rowHeights=[10*mm, 7*mm, 7*mm])
    company_head.setStyle(TableStyle([
        ("SPAN",(0,0),(-1,0)),
    ]))
    company_head.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.8,colors.black), ("LINEBELOW",(0,0),(-1,0),0.45,colors.black),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("ALIGN",(0,0),(0,0),"CENTER"),
        ("ALIGN",(0,1),(0,1),"LEFT"), ("ALIGN",(1,1),(1,1),"RIGHT"),
        ("FONTNAME",(0,1),(-1,1),"Helvetica-Bold"),
        ("LEFTPADDING",(0,0),(-1,-1),4), ("RIGHTPADDING",(0,0),(-1,-1),5),
    ]))
    story = [company_head, Spacer(1, 3), invoice_head, Spacer(1, 3)]
    party_block = Table([
        [para("M/s. " + str(party), bold), para("Mines : " + str(mines), bold)],
        [para(str(address), normal), para("Description of Transport Service : LIGNITE", normal)],
        [para("GSTIN No. : " + str(gstin), normal), para("DO No. : " + str(do_text), normal)],
        [para("PAN No. : " + str(pan), normal), para("Material : " + str(material), normal)],
        [para("Dear Sir, Please find below freight details.", bold), ""],
    ], colWidths=[94*mm, 88*mm])
    party_block.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),2),
        ("RIGHTPADDING",(0,0),(-1,-1),2),("TOPPADDING",(0,0),(-1,-1),1),
        ("BOTTOMPADDING",(0,0),(-1,-1),1),
    ]))
    story.extend([party_block, Spacer(1, 3)])
    heads = ["Sr.", "Date", "LR No.", "DO No.", "Truck No.", "Despatch Wt. (MT)", "Receipt Wt. (MT)", "Rate / TON", "Amount Rs."]
    header_style = ParagraphStyle("BillColumnHeaderBold", parent=center, fontName="Helvetica-Bold",
                                  fontSize=8.5, leading=10, textColor=colors.black, alignment=1, wordWrap="CJK")
    rows = [[para(x, header_style) for x in heads]]
    sum_desp = sum_rcpt = sum_amount = 0.0
    for i, item in enumerate(builties, 1):
        desp = num(item.get("despatch_weight") or item.get("qty"))
        rcpt = num(item.get("receipt_weight") or item.get("qty"))
        basis = str(bill.get("weight_basis") or "Both Less")
        if basis == "Despatch": bill_wt = desp
        elif basis == "Receipt": bill_wt = rcpt
        else: bill_wt = rcpt - desp
        rate = num(bill.get("rate_per_ton")) or num(item.get("sale_rate")) or num(item.get("freight_rate"))
        amount = bill_wt * rate
        sum_desp += desp; sum_rcpt += rcpt; sum_amount += amount
        rows.append([para(i, center), para(item.get("date") or "", center),
            para(item.get("builty_no") or "", center), para(item.get("do_no") or "", center),
            para(item.get("truck_no") or "", center), para(wt(desp), right),
            para(wt(rcpt), right), para(money(rate), right), para(money(amount), right)])
    # Keep a large blank table area, matching the sample invoice's printable stationery.
    while len(rows) < 17:
        rows.append(["", "", "", "", "", "", "", "", ""])
    rows.append([para("TOTAL", bold), "", "", "", "",
        para(wt(sum_desp), bold), para(wt(sum_rcpt), bold), "",
        para(money(sum_amount), bold)])
    table = Table(rows, colWidths=[9*mm, 18*mm, 16*mm, 19*mm, 23*mm, 19*mm, 19*mm, 30*mm, 29*mm],
                  rowHeights=[10*mm]+[7.2*mm]*(len(rows)-2)+[8*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.75,colors.black),("INNERGRID",(0,0),(-1,-1),0.45,colors.black),
        ("BACKGROUND",(0,0),(-1,0),colors.whitesmoke),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,0),8.5),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("LEFTPADDING",(0,0),(-1,-1),2),("RIGHTPADDING",(0,0),(-1,-1),2),
        ("TOPPADDING",(0,0),(-1,-1),1),("BOTTOMPADDING",(0,0),(-1,-1),1),
    ]))
    story.extend([table, Spacer(1, 2)])
    subtotal = num(bill.get("subtotal")) or sum_amount
    cgst, sgst, igst = num(bill.get("cgst")), num(bill.get("sgst")), num(bill.get("igst"))
    round_off = num(bill.get("round_off"))
    total = num(bill.get("total")) or subtotal + cgst + sgst + igst + round_off
    bank = str(firm.get("bank_details") or "").strip()
    if not bank:
        bank_parts = [
            ("Bank Name", firm.get("bank_name")), ("A/c No.", firm.get("account_no")),
            ("IFSC", firm.get("ifsc_code")), ("Branch", firm.get("branch_name")),
        ]
        bank = " | ".join(label + ": " + str(value).strip() for label, value in bank_parts if str(value or "").strip())
    terms_box = Table([
        [para("Terms &amp; Conditions", bold)],
        [para("1. Subject to Bhuj Jurisdiction.", normal)],
        [para("2. GST - RCM not apply if otherwise agreed.", normal)],
        [para("3. Paid By Receiver", normal)],
    ], colWidths=[96*mm], rowHeights=[6*mm,6*mm,6*mm,6*mm])
    terms_box.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.7,colors.black),
        ("LINEBELOW",(0,0),(-1,0),0.5,colors.black),
        ("FONTNAME",(0,3),(0,3),"Helvetica"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),5), ("RIGHTPADDING",(0,0),(-1,-1),4),
        ("TOPPADDING",(0,0),(-1,-1),1), ("BOTTOMPADDING",(0,0),(-1,-1),1),
    ]))
    bank_text = para("<b>BANK DETAILS</b><br/>" + (bank if bank else "Bank Details :"), normal)
    totals = Table([
        [terms_box, para("SUB TOTAL", bold), para(money(subtotal), bold)],
        ["", para("CGST", bold), para(money(cgst), bold)],
        ["", para("SGST", bold), para(money(sgst), bold)],
        ["", bank_text, ""],
        ["", para("IGST", bold), para(money(igst), bold)],
        ["", para("Round Off", bold), para(money(round_off), bold)],
        ["", para("NET AMOUNT", bold), para(money(total), bold)],
        [para("Rupees : " + str(bill.get("amount_in_words") or ""), normal), "", ""],
    ], colWidths=[96*mm, 42*mm, 44*mm], rowHeights=[24*mm,7*mm,7*mm,10*mm,7*mm,7*mm,8*mm,7*mm])
    totals.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.55,colors.black),("INNERGRID",(0,0),(-1,-1),0.3,colors.black),
        ("SPAN",(1,3),(2,3)),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),3),
        ("RIGHTPADDING",(0,0),(-1,-1),3),("TOPPADDING",(0,0),(-1,-1),1),
        ("BOTTOMPADDING",(0,0),(-1,-1),1),
    ]))
    signature = Table([["", para("For " + firm_name, bold)]], colWidths=[122*mm, 60*mm], rowHeights=[14*mm])
    signature.setStyle(TableStyle([("ALIGN",(1,0),(1,0),"RIGHT"),("VALIGN",(0,0),(-1,-1),"BOTTOM"),("FONTNAME",(1,0),(1,0),"Helvetica-Bold")]))
    story.extend([totals, Spacer(1, 3), signature])
    doc.build(story)
    return str(out_path)


class _ChitTruck(Flowable):
    """Small vector truck emblem for the loading chit header."""
    def __init__(self):
        super().__init__()
        self.width = 32*mm
        self.height = 25*mm
    def wrap(self, availWidth, availHeight):
        return (self.width, self.height)
    def draw(self):
        canvas = self.canv
        x, y = 0, 0
        canvas.saveState()
        canvas.setLineWidth(1.1)
        canvas.rect(x+2*mm, y+7*mm, 23*mm, 10*mm)
        for i in range(5):
            canvas.line(x+(3+i*4)*mm, y+8*mm, x+(3+i*4)*mm, y+16*mm)
        canvas.rect(x+25*mm, y+7*mm, 6*mm, 7*mm)
        canvas.line(x+26*mm, y+12*mm, x+30*mm, y+12*mm)
        canvas.circle(x+8*mm, y+5*mm, 2*mm)
        canvas.circle(x+26*mm, y+5*mm, 2*mm)
        canvas.restoreState()


def generate_chit_pdf(out_path, firm, builty, do_row):
    """English mine-loading chit for Mansi Coal Carriers."""
    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
        leftMargin=13*mm, rightMargin=13*mm, topMargin=7*mm, bottomMargin=7*mm)
    normal = ParagraphStyle("ChitEnglishNormal", parent=CELL, fontName=font_regular,
                            fontSize=10, leading=12, wordWrap="CJK")
    bold = ParagraphStyle("ChitEnglishBold", parent=normal, fontName=font_bold)
    title = ParagraphStyle("ChitEnglishTitle", parent=normal, fontName=font_bold,
                           fontSize=18, leading=21, alignment=1)
    subtitle = ParagraphStyle("ChitEnglishSub", parent=normal, fontName=font_regular,
                              fontSize=9, leading=11, alignment=1)
    def para(v="", style=normal, limit=350):
        return Paragraph(_safe(v, limit), style)
    def first(*values):
        for value in values:
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""
    firm_name = "MANSI COAL CARRIERS"
    office = "Office No. 1, Behind Sadguru Complex, Bhuj Madhapar Highway, Bhuj-Kutch."
    party = first(do_row.get("customer_name"), builty.get("consignee"))
    village = first(do_row.get("to_place"), builty.get("to_place"), builty.get("center_name"))
    do_number = first(do_row.get("do_no"), do_row.get("gmdc_do_no"))
    reg_no = first(do_row.get("registration_no"), do_row.get("regi_no"), do_row.get("reg_no"))
    do_date = first(do_row.get("date"), do_row.get("do_date"))
    truck_no = first(builty.get("truck_no"), builty.get("vehicle_no"))
    chit_no = first(builty.get("builty_no"), builty.get("lr_no"), builty.get("id"))

    office_style = ParagraphStyle("ChitOffice", parent=normal, fontName=font_bold,
                                   fontSize=8.5, leading=11, alignment=1)
    phone_style = ParagraphStyle("ChitPhone", parent=bold, alignment=1, fontSize=9, leading=11)
    header = Table([
        [[para(firm_name, title),
          para("Transport Contractor & Lignite Clearing Agent", subtitle),
          para(office, office_style, 220)],
         [para("For MANSI COAL CARRIERS", phone_style),
          para("Md. 98795 09226 / 90160 11092", phone_style)]],
    ], colWidths=[128*mm, 57*mm], rowHeights=[32*mm])
    header.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.9,colors.HexColor("#123D78")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("ALIGN",(0,0),(0,0),"CENTER"),
        ("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
    ]))
    tons_circle = Table([[para("24 Tons", bold)]], colWidths=[25*mm], rowHeights=[25*mm])
    tons_circle.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0,colors.white),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("LEFTPADDING",(0,0),(-1,-1),1),("RIGHTPADDING",(0,0),(-1,-1),1),
    ]))
    # Draw a circular outline around the quantity using a custom flowable cell.
    class _CircleTons(Flowable):
        def __init__(self, text, style):
            super().__init__()
            self.text, self.style = text, style
            self.width, self.height = 25*mm, 25*mm
        def wrap(self, availWidth, availHeight):
            return (self.width, self.height)
        def draw(self):
            self.canv.saveState()
            self.canv.setLineWidth(0.9)
            self.canv.circle(self.width/2, self.height/2, 11*mm)
            p = Paragraph(self.text, self.style)
            w, h = p.wrap(22*mm, 20*mm)
            p.drawOn(self.canv, (self.width-w)/2, (self.height-h)/2)
            self.canv.restoreState()
    quantity = _CircleTons("24 Tons", bold)
    grade_code = Table([
        [para("Grade 'A'", bold)],
        [para("CODE NO: M595", bold)],
    ], colWidths=[37*mm], rowHeights=[11*mm, 11*mm])
    grade_code.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.8,colors.black),("INNERGRID",(0,0),(-1,-1),0.55,colors.black),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),
    ]))
    number_date = Table([[
        para("No. " + (chit_no or "........................"), bold),
        para("Date: ................................", bold)
    ]], colWidths=[92.5*mm, 92.5*mm], rowHeights=[9*mm])
    number_date.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.8,colors.black),("INNERGRID",(0,0),(-1,-1),0.5,colors.black),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
    ]))
    addressee = Table([
        [para("To,", bold)],
        [para("Shri Mines Manager Sir,", bold)],
        [para("G.M.D.C.L.", bold)],
        [para("Lignite Project Matanamadh", bold)],
    ], colWidths=[110*mm], rowHeights=[7*mm, 8*mm, 7*mm, 8*mm])
    addressee.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),3),
    ]))
    right_info = Table([[quantity], [grade_code]], colWidths=[75*mm], rowHeights=[25*mm, 22*mm])
    right_info.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("LEFTPADDING",(0,0),(-1,-1),2),("RIGHTPADDING",(0,0),(-1,-1),2),
    ]))
    # One outer box contains the complete address/instruction block.
    # Quantity stays circled; Grade and Code each have their own stacked box.
    intro = para("Sir, Jai Bharat. We request you to load the truck with good-quality lignite, without powder, as per the details of our party's D.O. given below.", normal)
    grade = Table([[para("'A' Loose Lignite", bold)]], colWidths=[185*mm], rowHeights=[9*mm])
    grade.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.8,colors.black),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    recipient_block = Table([
        [addressee, right_info],
        [intro, ""],
        [grade, ""],
    ], colWidths=[110*mm, 75*mm], rowHeights=[57*mm, 17*mm, 11*mm])
    recipient_block.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.9,colors.black),
        ("INNERGRID",(0,0),(-1,-1),0.5,colors.black),
        ("SPAN",(0,1),(-1,1)),("SPAN",(0,2),(-1,2)),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
    ]))
    details_data = [
        [para("Party Name:", bold), para(party)],
        [para("Village Name:", bold), para(village)],
        [para("D.O. No.:", bold), para(do_number)],
        [para("Reg. No.:", bold), para(reg_no)],
        [para("D.O. Date:", bold), para(do_date)],
        [para("Truck No.:", bold), para(truck_no)],
    ]
    details = Table(details_data, colWidths=[52*mm, 133*mm], rowHeights=[12*mm]*6)
    details.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.9,colors.black),("INNERGRID",(0,0),(-1,-1),0.65,colors.black),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
    ]))
    instructions = Table([
        [para("Instructions for Vehicle Owners / Drivers:", bold)],
        [para("Check the lignite at the mine before loading. If the lignite contains salt, stones, soil, or water, the responsibility will be yours.", normal)],
    ], colWidths=[185*mm], rowHeights=[10*mm, 18*mm])
    instructions.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.8,colors.black),("INNERGRID",(0,0),(-1,-1),0.5,colors.black),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),5),
        ("RIGHTPADDING",(0,0),(-1,-1),5),
    ]))
    footer = Table([[para("For Mansi Coal Carriers", bold)]], colWidths=[185*mm], rowHeights=[16*mm])
    footer.setStyle(TableStyle([("ALIGN",(0,0),(-1,-1),"RIGHT"),("VALIGN",(0,0),(-1,-1),"BOTTOM"),
        ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),8)]))
    story = [header, Spacer(1, 3*mm), number_date, Spacer(1, 1*mm), recipient_block, Spacer(1, 2*mm),
             details, Spacer(1, 2*mm), instructions, footer]
    doc.build(story)
    return str(out_path)

