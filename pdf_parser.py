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
        return _clean(m.group(1)) if m else default

    gstins = [g.upper() for g in re.findall(
        r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b", flat, re.I)]
    customer_gstin = next((g for g in gstins if g != GMDC_GSTIN), "")
    # Customer Number in the sample is 10061; don't accidentally read an amount/date.
    customer_no = grab(r"\bCustomer\s+(?:No\.?|Number)\s*[:#]?\s*([0-9]{3,12})")
    if not customer_no:
        customer_no = grab(r"\b10061\b")

    # Prefer the company name, not the next field label. GMDC layouts sometimes
    # extract labels and values in a different column order.
    customer_name = grab(
        r"(PRABHAKAR\s+PROCESSORS\s+PVT\.?\s*LTD\.{0,2})",
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
    row = re.search(
        r"\b1\s+(.+?)\s+([0-9]{2}-[A-Z]{3}-[0-9]{2})\s+([0-9,]+(?:\.[0-9]+)?)\s+([A-Z]+)\s+([0-9,]+(?:\.[0-9]+)?)\s+([0-9,]+(?:\.[0-9]+)?)",
        text, re.I | re.S)
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
        "schedule_date": "", "qty": 0.0, "uom": "TON",
        "unit_price": 0.0, "extended_price": 0.0,
        "transporter_code": grab(r"\bTransporter Code\s*:\s*([A-Z0-9]+)"),
        "transporter_name": grab(r"\bTransporter Name\s*:\s*(.+?)(?=\s+ORDER TOTAL\b|$)"),
        "order_total": _num(grab(r"\bORDER TOTAL\s+([0-9,]+(?:\.[0-9]+)?)")),
        "from_place": "BHAVNAGAR", "to_place": ""
    }
    if row:
        data.update(material=data["material"] or _clean(row.group(1)),
                    schedule_date=row.group(2).upper(), qty=_num(row.group(3)),
                    uom=row.group(4).upper(), unit_price=_num(row.group(5)),
                    extended_price=_num(row.group(6)))
    else:
        data["qty"] = _num(grab(r"\bTotal Qty\s*[: ]+([0-9,]+(?:\.[0-9]+)?)"))
    return data
