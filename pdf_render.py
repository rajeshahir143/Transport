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
    story = [para(firm_name, title), Spacer(1, 8),
             para(str(firm.get("gstin") or ""), normal),
             Table([[para("No. : " + str(bill_no), bold), para(invoice_label, title),
                     para("Date : " + str(bill_date), bold)]],
                   colWidths=[55*mm, 75*mm, 52*mm]),
             Spacer(1, 3)]
    party_block = Table([
        [para("M/s. " + str(party), bold), para("Mines : " + str(mines), bold)],
        [para(str(address), normal), para("Description of Transport Service : LIGNITE", normal)],
        [para("GSTIN No. : " + str(gstin), normal), para("DO No. : " + str(do_text), normal)],
        [para("PAN No. : " + str(pan), normal), para("Material : " + str(material), normal)],
        [para("Dear Sir,   Please find below freight details :-", normal), ""],
    ], colWidths=[94*mm, 88*mm])
    party_block.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),2),
        ("RIGHTPADDING",(0,0),(-1,-1),2),("TOPPADDING",(0,0),(-1,-1),1),
        ("BOTTOMPADDING",(0,0),(-1,-1),1),
    ]))
    story.extend([party_block, Spacer(1, 3)])
    story.append(para("Rate Rs. (rate entered on this Bill)", normal))
    heads = ["Sr.", "Date", "LR No.", "DO No.", "Truck No.", "Despatch\nWt. (MT)", "Receipt\nWt. (MT)", "Rate / TON", "Amount Rs."]
    rows = [[para(x, center if i != 0 else bold) for i,x in enumerate(heads)]]
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
        ("BOX",(0,0),(-1,-1),0.65,colors.black),("INNERGRID",(0,0),(-1,-1),0.35,colors.black),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("LEFTPADDING",(0,0),(-1,-1),2),("RIGHTPADDING",(0,0),(-1,-1),2),
        ("TOPPADDING",(0,0),(-1,-1),1),("BOTTOMPADDING",(0,0),(-1,-1),1),
    ]))
    story.extend([table, Spacer(1, 2)])
    subtotal = num(bill.get("subtotal")) or sum_amount
    cgst, sgst, igst = num(bill.get("cgst")), num(bill.get("sgst")), num(bill.get("igst"))
    round_off = num(bill.get("round_off"))
    total = num(bill.get("total")) or subtotal + cgst + sgst + igst + round_off
    terms = "Terms & Conditions :\nSubject to Bhuj Jurisdiction.\nGST - RCM not apply if otherwise agreed.\n* Paid By Receiver"
    bank = str(firm.get("bank_details") or "Bank Details :")
    totals = Table([
        [para(terms, normal), para("TOTAL", bold), para(money(subtotal), bold)],
        [para(bank, normal), para("CGST 9.00%", normal), para(money(cgst), right)],
        ["", para("SGST 9.00%", normal), para(money(sgst), right)],
        ["", para("IGST", normal), para(money(igst), right)],
        ["", para("Round Off", normal), para(money(round_off), right)],
        ["", para("Net Amount", bold), para(money(total), bold)],
        [para("Rupees : " + str(bill.get("amount_in_words") or ""), normal), "", ""],
    ], colWidths=[96*mm, 42*mm, 44*mm], rowHeights=[13*mm,7*mm,7*mm,7*mm,7*mm,8*mm,7*mm])
    totals.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.55,colors.black),("INNERGRID",(0,0),(-1,-1),0.3,colors.black),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),3),
        ("RIGHTPADDING",(0,0),(-1,-1),3),("TOPPADDING",(0,0),(-1,-1),1),
        ("BOTTOMPADDING",(0,0),(-1,-1),1),
    ]))
    signature = Table([[para("For " + firm_name, bold)]], colWidths=[182*mm], rowHeights=[14*mm])
    signature.setStyle(TableStyle([("ALIGN",(0,0),(-1,-1),"RIGHT"),("VALIGN",(0,0),(-1,-1),"BOTTOM")]))
    story.extend([totals, signature])
    doc.build(story)
    return str(out_path)


class _ChitTruck:
    """Small vector truck emblem for the loading chit header."""
    def wrap(self, availWidth, availHeight):
        return (32*mm, 25*mm)
    def drawOn(self, canvas, x, y, _sW=0):
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
    """Gujarati mine-loading chit; use a Gujarati-capable, HarfBuzz-shaped font."""
    import os
    from pathlib import Path
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"
    # Windows Nirmala UI contains Gujarati glyphs; use HarfBuzz shaping for conjuncts.
    font_candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "Nirmala.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "NirmalaS.ttf",
        Path(__file__).resolve().parent / "fonts" / "NotoSansGujarati-Regular.ttf",
    ]
    bold_candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "NirmalaB.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "NirmalaS-Bold.ttf",
    ]
    font_path = next((p for p in font_candidates if p.is_file()), None)
    if font_path:
        try:
            if "ChitGujarati" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("ChitGujarati", str(font_path), shapable=True))
            font_regular = "ChitGujarati"
            bold_path = next((p for p in bold_candidates if p.is_file()), None)
            if bold_path:
                if "ChitGujaratiBold" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("ChitGujaratiBold", str(bold_path), shapable=True))
                font_bold = "ChitGujaratiBold"
            else:
                font_bold = font_regular
            pdfmetrics.registerFontFamily("ChitGujarati", normal=font_regular,
                                          bold=font_bold, italic=font_regular, boldItalic=font_bold)
        except Exception:
            # Do not silently produce boxes for Gujarati; fail with a clear installation message.
            raise RuntimeError(
                "Gujarati font shaping is unavailable. Install Nirmala UI and uharfbuzz, then retry Chit Print."
            )

    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
        leftMargin=13*mm, rightMargin=13*mm, topMargin=7*mm, bottomMargin=7*mm)
    normal = ParagraphStyle("ChitGujaratiNormal", parent=CELL, fontName=font_regular,
                            fontSize=10, leading=15, wordWrap="CJK")
    bold = ParagraphStyle("ChitGujaratiBoldStyle", parent=normal, fontName=font_bold)
    title = ParagraphStyle("ChitGujaratiTitle", parent=normal, fontName=font_bold,
                           fontSize=20, leading=24, alignment=1)
    subtitle = ParagraphStyle("ChitGujaratiSub", parent=normal, fontName=font_regular,
                              fontSize=9, leading=12, alignment=1)
    center = ParagraphStyle("ChitGujaratiCenter", parent=normal, alignment=1)
    def para(v="", style=normal, limit=350):
        return Paragraph(_safe(v, limit), style)
    def first(*values):
        for value in values:
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""
    raw_name = str(firm.get("name") or "MANSI COAL CARRIER").strip()
    firm_key = raw_name.upper()
    gujarati_names = {
        "MANSI COAL CARRIER": "માનસી કોલ કેરીયર્સ",
        "MANSI COAL CAREER": "માનસી કોલ કેરીયર્સ",
        "MANSI COAL CARRIER.": "માનસી કોલ કેરીયર્સ",
        "MANSI COAL CAREER.": "માનસી કોલ કેરીયર્સ",
        "PARTH ENTERPRISE": "પાર્થ એન્ટરપ્રાઇઝ",
        "SHIVAY LOGISTICS": "શિવાય લોજિસ્ટિક્સ",
        "SHREE RAMDEV ENTERPRISE.": "શ્રી રામદેવ એન્ટરપ્રાઇઝ",
        "K. D. ENTERPRISE": "કે. ડી. એન્ટરપ્રાઇઝ",
        "NILKANTH LOGISTICS": "નીલકંઠ લોજિસ્ટિક્સ",
        "M R ENTERPRISE": "એમ આર એન્ટરપ્રાઇઝ",
    }
    firm_name = gujarati_names.get(firm_key, raw_name)
    office = first(firm.get("address"),
        "ઓફિસ નંબર ૧, સદગુરૂ કોમ્પ્લેક્ષની પાછળ, ભુજ માધાપર હાઈવે, ભુજ-કચ્છ.")
    party = first(do_row.get("customer_name"), builty.get("consignee"))
    village = first(do_row.get("to_place"), builty.get("to_place"), builty.get("center_name"))
    do_number = first(do_row.get("do_no"), do_row.get("gmdc_do_no"))
    reg_no = first(do_row.get("registration_no"), do_row.get("regi_no"), do_row.get("reg_no"))
    do_date = first(do_row.get("date"), do_row.get("do_date"))
    truck_no = first(builty.get("truck_no"), builty.get("vehicle_no"))
    chit_no = first(builty.get("builty_no"), builty.get("lr_no"), builty.get("id"))

    header = Table([
        [_ChitTruck(), [para(firm_name, title), para("ટ્રાન્સપોર્ટ કોન્ટ્રાકટર એન્ડ લીગ્નાઇટ કલીયરીંગ એજન્ટ", subtitle)]],
        ["", para(office, subtitle)],
        ["", para("મો. ૯૮૭૯૫ ૦૯૨૨૬ ૮૦૧૬૦ ૧૧૦૮૨", bold)],
    ], colWidths=[35*mm, 150*mm], rowHeights=[20*mm, 8*mm, 7*mm])
    header.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.9,colors.black),
        ("LINEBELOW",(0,1),(-1,1),0.6,colors.black),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("ALIGN",(1,0),(1,-1),"CENTER"),
        ("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
    ]))
    top = Table([
        [para("નં. " + chit_no, bold), para("તા. ................................", bold), para("૨૪ ટન", bold)],
        [para("પ્રતિ,", bold), para("શ્રી માઈન્સ મેનેજર સાહેબ,", bold), para("ગ્રેડ 'A'\\nકોડ નં.: M595", bold)],
        [para("જી.એમ.ડી.સી.લી.", bold), para("લિગ્નાઈટ પ્રોજેકટ માતાનામઢ", bold), para("", normal)],
    ], colWidths=[55*mm, 75*mm, 55*mm], rowHeights=[10*mm, 9*mm, 9*mm])
    top.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.8,colors.black),("INNERGRID",(0,0),(-1,-1),0.55,colors.black),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(2,0),(2,-1),"CENTER"),
        ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
    ]))
    intro = para("સાહેબ શ્રી, જય ભારત સાથે જણાવવાનું કે નીચેની વિગતે અમારી પાર્ટીના ડી.ઓ. મુજબનો સારો ભુક્કા વગરનો લિગ્નાઈટ આવેલ ટ્રકમાં ભરી આપવા વિનંતી છે.", normal)
    grade = Table([[para("'A' લુઝ લિગ્નાઈટ", bold, 120)]], colWidths=[185*mm], rowHeights=[9*mm])
    grade.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.8,colors.black),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    details_data = [
        [para("પાર્ટીનું નામ :", bold), para(party)],
        [para("ગામનું નામ :", bold), para(village)],
        [para("ડી.ઓ. નં. :", bold), para(do_number)],
        [para("રજી. નં. :", bold), para(reg_no)],
        [para("ડી.ઓ. તા. :", bold), para(do_date)],
        [para("ટ્રક નંબર :", bold), para(truck_no)],
    ]
    details = Table(details_data, colWidths=[52*mm, 133*mm], rowHeights=[11*mm]*6)
    details.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.9,colors.black),("INNERGRID",(0,0),(-1,-1),0.65,colors.black),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
    ]))
    instructions = Table([
        [para("ગાડી માલિક / ડ્રાઈવરો માટે સૂચના :", bold)],
        [para("માઇન્સ પરથી લિગ્નાઈટ જોઈ તપાસીને ભરવો, લિગ્નાઈટમાં સેલ, પથ્થર, માટી કે પાણી આવશે તો તેની જવાબદારી આપની રહેશે.", normal)],
    ], colWidths=[185*mm], rowHeights=[9*mm, 16*mm])
    instructions.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.8,colors.black),("INNERGRID",(0,0),(-1,-1),0.5,colors.black),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),5),
        ("RIGHTPADDING",(0,0),(-1,-1),5),
    ]))
    footer = Table([[para("માનસી કોલ કેરીયર્સ વતી,", bold)]], colWidths=[185*mm], rowHeights=[16*mm])
    footer.setStyle(TableStyle([("ALIGN",(0,0),(-1,-1),"RIGHT"),("VALIGN",(0,0),(-1,-1),"BOTTOM"),
        ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),8)]))
    story = [header, Spacer(1, 3*mm), top, Spacer(1, 2*mm), intro, Spacer(1, 2*mm),
             grade, Spacer(1, 2*mm), details, Spacer(1, 2*mm), instructions, footer]
    doc.build(story)
    return str(out_path)
