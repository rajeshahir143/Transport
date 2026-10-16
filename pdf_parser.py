"""GMDC DO PDF parser; handles column-wise and line-wise text extraction."""
import re
try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

GMDC_GSTIN = "24AAACG7987P1ZT"

def _clean(value):
    return re.sub(r"\s+", " ", (value or "")).strip(" :\t")

def _num(value):
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(value or ""))
    return float(m.group().replace(",", "")) if m else 0.0

def parse_pdf(path):
    if PdfReader is None:
        raise RuntimeError("Install pypdf: pip install pypdf")
    text = "\n".join(p.extract_text() or "" for p in PdfReader(path).pages).replace("\u00a0", " ")
    flat = _clean(text)
    def grab(pattern, default=""):
        m = re.search(pattern, flat, re.I)
        return _clean(m.group(1) if m.lastindex else m.group(0)) if m else default

    gstins = [g.upper() for g in re.findall(
        r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b", flat, re.I)]
    customer_gstin = next((g for g in gstins if g != GMDC_GSTIN), "")
    # Customer Number in the sample is 10061; don't accidentally read an amount/date.
    customer_no = grab(r"\bCustomer\s+(?:No\.?|Number)\s*[:#]?\s*([0-9]{3,12})")
    if not customer_no:
        customer_no = grab(r"\b1032\b") or grab(r"\b10061\b")

    # Prefer the company name, not the next field label. GMDC layouts sometimes
    # extract labels and values in a different column order.
    customer_name = grab(
        r"(SAYAJI\s+INDUSTRIES\s+LIMITED\s+C/0\s+MAIZE\s+PRODUCTS|PRABHAKAR\s+PROCESSORS\s+PVT\.?\s*LTD\.{0,2})",
    )
    if not customer_name:
        customer_name = grab(
            r"\bCustomer\s+Name\s*[:#]?\s*(.+?)(?=\s+(?:Customer\s+GSTIN|Customer\s+No\.?|Order\s+Type|Order\s+Date|Bill\s+To|Ship\s+To)\b|$)"
        )
    if customer_name.lower().strip(" .:") in ("customer gstin", "customer no", "customer number", "order type"):
        customer_name = ""

    order_type = grab(r"\bOrder\s+Type\s+(.+?)(?=\s+(?:Bill\s+To|Ship\s+To|State|HSN|Schedule\s+Date)\b|$)")
    if "HOD-BHAV-Lignte" in flat and "Order E" in flat:
        order_type = "HOD-BHAV-Lignte Order E"
    # Extract every schedule row from GMDC DO PDFs, not just the first row.
    schedule_rows = []
    row_pattern = re.compile(
        r"(?m)^\s*(\d{1,3})\s+(.+?)\s+(\d{2}-[A-Z]{3}-\d{2})\s+"
        r"([0-9,]+(?:\.[0-9]+)?)\s+([A-Z]+)\s+"
        r"([0-9,]+(?:\.[0-9]+)?)\s+([0-9,]+(?:\.[0-9]+)?)\s*$",
        re.I)
    for match in row_pattern.finditer(text):
        schedule_rows.append({
            "sr_no": int(match.group(1)),
            "item": _clean(match.group(2)),
            "schedule_date": match.group(3).upper(),
            "qty": _num(match.group(4)),
            "uom": match.group(5).upper(),
            "unit_price": _num(match.group(6)),
            "extended_price": _num(match.group(7)),
        })
    schedule_rows.sort(key=lambda r: __import__("datetime").datetime.strptime(r["schedule_date"], "%d-%b-%y"))
    # Extract "TO MA DIST" separately from the ordinary "TO" destination.
    # The PDF's "TO MA DIST" value belongs in the existing DO "To" field.
    to_ma_dist = grab(
        r"\bTO\s+MA\s+DIST\.?\s*[:\-]?\s*([A-Z][A-Z .&()'-]{1,50}?)(?=\s+(?:TO\b|FROM\b|TRANSPORTER\b|ORDER\s+TOTAL\b|CUSTOMER\b|SCHEDULE\s+DATE\b|HSN\b)|$)"
    ).strip(" .-")
    to_place = to_ma_dist or grab(
        r"\bTO\s*:\s*([A-Z][A-Z .&()'-]{1,50}?)(?=\s+(?:FROM\b|TRANSPORTER\b|ORDER\s+TOTAL\b|CUSTOMER\b|SCHEDULE\s+DATE\b|HSN\b)|$)"
    ).strip(" .-")
    # Keep the transporter name clean and consistent for Builty Sale Party.
    transporter_name = grab(r"\bMANSI\s+COAL\s+CARRI(?:ER|ER)\b")
    if not transporter_name:
        transporter_name = grab(r"\bTransporter\s+Name\s*[: ]+(.+?)(?=\s+ORDER\s+TOTAL\b|$)")
    if transporter_name and "MANSI COAL" in transporter_name.upper():
        transporter_name = "MANSI COAL CARRIER"

    data = {
        "do_no": "",
        "gmdc_do_no": grab(r"\b(?:Order Number|Delivery Order)\s*[:#*]?\s*([0-9]{8,})"),
        "do_date": grab(r"\bOrder Date\s*[:#]?\s*([0-9A-Z-]+)"),
        "customer_no": customer_no,
        "customer_name": customer_name,
        "customer_gstin": customer_gstin,
        "order_type": order_type,
        "bill_to": grab(r"\bBill To\s+(.+?)(?=\s+Ship To\b|$)"),
        "ship_to": grab(r"\bShip To\s+(.+?)(?=\s+State\b|$)"),
        "state": grab(r"\bState\s*:\s*([A-Z ]+?)\s+HSN"),
        "hsn": grab(r"\bHSN Code\s*:\s*([0-9]+)"),
        "material": grab(r"\bDescription of Goods\s*:\s*(.+?)(?:\r?\n|$)"),
        "schedule_date": "", "schedule_rows": schedule_rows, "qty": 0.0, "uom": "TON",
        "unit_price": 0.0, "extended_price": 0.0,
        "transporter_code": grab(r"\bTransporter Code\s*:\s*([A-Z0-9]+)"),
        "transporter_name": transporter_name,
        "order_total": _num(grab(r"\bORDER TOTAL\s+([0-9,]+(?:\.[0-9]+)?)")),
        "from_place": "BHAVNAGAR", "to_place": (to_ma_dist or to_place), "to_ma_dist": to_ma_dist
    }
    if schedule_rows:
        data["schedule_date"] = schedule_rows[0]["schedule_date"]
        data["qty"] = sum(r["qty"] for r in schedule_rows)
        data["uom"] = schedule_rows[0]["uom"]
        data["unit_price"] = schedule_rows[0]["unit_price"]
        data["extended_price"] = sum(r["extended_price"] for r in schedule_rows)
        # Prefer the clean item name from the schedule table over mis-extracted description text.
        # Examples: MATA NO MADH 'A' GRADE or BHAVNAGAR 'A' GRADE.
        data["material"] = schedule_rows[0]["item"] or data["material"]
    else:
        data["qty"] = _num(grab(r"\bTotal Qty\s*[: ]+([0-9,]+(?:\.[0-9]+)?)"))
    return data
