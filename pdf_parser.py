"PDF parsing for GMDC Delivery Order PDFs.

The GMDC PDF text extractor may emit labels and values on separate lines OR
multiple columns on the same line. Keep field extraction tolerant of both.
"""
import re

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None


def _num(s):
    if s is None:
        return 0.0
    s = str(s).replace(",", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    try:
        return float(m.group()) if m else 0.0
    except Exception:
        return 0.0


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip(" \t:-")


def _label_value(text, label, stop_labels=()):
    """Get a value after a label, including when PDF columns share a line."""
    labels = ("Customer Number", "Customer Name", "Customer GSTIN", "Order Number",
              "Order Date", "Order Type", "Bill To", "Ship To", "State",
              "HSN Code", "Description of Goods", "Transporter Code",
              "Transporter Name", "ORDER TOTAL", "Total Qty")
    stops = list(stop_labels) or [x for x in labels if x.lower() != label.lower()]
    stop = "|".join(re.escape(x) for x in sorted(stops, key=len, reverse=True))
    # Value can start on the same line or next line; stop before another known label.
    pattern = rf"{re.escape(label)}\s*:?\s*(.*?)(?=\s+(?:{stop})\b|\s*\n\s*(?:{stop})\b|$)"
    m = re.search(pattern, text, re.I | re.S)
    return _clean(m.group(1)) if m else ""


def parse_pdf(path):
    """Extract Delivery Order fields from GMDC PDF text, including column layouts."""
    if PdfReader is None:
        raise RuntimeError("pypdf is not installed. Run: pip install pypdf")

    text = "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)
    text = text.replace("\r", "\n")
    # Normalize PDF whitespace but preserve line boundaries for date/table matching.
    text = re.sub(r"[ \t]+", " ", text)

    def grab(pattern, default=""):
        m = re.search(pattern, text, re.I | re.M | re.S)
        return _clean(m.group(1)) if m else default

    data = {
        "do_no": grab(r"Order Number\s*:?\s*([0-9]+)",
                      grab(r"Delivery Order\s*\*?([0-9]+)\*?")),
        "do_date": grab(r"Order Date\s*:?\s*([0-9A-Z-]+)"),
        "customer_no": "",
        "customer_name": "",
        "customer_gstin": "",
        "order_type": "",
        "bill_to": "",
        "ship_to": "",
        "state": "",
        "hsn": "",
        "material": "",
        "schedule_date": "",
        "transporter_code": "",
        "transporter_name": "",
        "from_place": "BHAVNAGAR",
        "to_place": "",
    }

    # Prefer exact labelled values; fallback to line/column-aware patterns.
    data["customer_no"] = grab(r"Customer Number\s*:?\s*([0-9]{3,})")
    if not data["customer_no"]:
        data["customer_no"] = _label_value(text, "Customer Number")
    data["customer_gstin"] = grab(r"Customer GSTIN\s*:?\s*((?:[0-9]{2})[A-Z0-9]{10,})")
    if not data["customer_gstin"]:
        # GSTIN is a 15-character alphanumeric token. Do not mistake customer number for GSTIN.
        candidates = re.findall(r"\b[0-9]{2}[A-Z]{4,5}[0-9A-Z]{8,9}\b", text)
        data["customer_gstin"] = next((v for v in candidates if v != grab(r"GSTIN\s*:?\s*([0-9A-Z]+)")), "")
    data["customer_name"] = _label_value(
        text, "Customer Name",
        ("Customer GSTIN", "Customer Number", "Order Number", "Order Date", "Order Type",
         "Bill To", "Ship To", "State", "HSN Code", "Description of Goods",
         "Transporter Code", "Transporter Name", "ORDER TOTAL")
    )
    if not data["customer_name"]:
        m = re.search(r"Customer Name\s*:?\s*\n?\s*(.{2,100}?)(?=\n\s*(?:Customer GSTIN|GSTIN|Customer Number|Order Type)\b)", text, re.I | re.S)
        if m:
            data["customer_name"] = _clean(m.group(1))
    data["order_type"] = _label_value(text, "Order Type")
    data["bill_to"] = _label_value(text, "Bill To", ("Ship To", "State", "HSN Code", "Description of Goods"))
    data["ship_to"] = _label_value(text, "Ship To", ("State", "HSN Code", "Description of Goods", "Transporter Code"))
    data["state"] = grab(r"State\s*:\s*([A-Z ]+?)\s+HSN")
    data["hsn"] = grab(r"HSN Code\s*:\s*([0-9]+)")
    data["material"] = grab(r"Description of Goods\s*:\s*(.+?)(?:\n|$)")
    data["transporter_code"] = grab(r"Transporter Code\s*:\s*([A-Z0-9]+)")
    data["transporter_name"] = grab(r"Transporter Name\s*:\s*(.+?)(?:\n|$)")

    # GMDC item table: item, schedule date, quantity, UOM, unit price, extended price.
    m = re.search(
        r"\b1\s+(.+?)\s+([0-9]{2}-[A-Z]{3}-[0-9]{2})\s+([0-9,.]+)\s+([A-Z]+)\s+([0-9,.]+)\s+([0-9,.]+)",
        text, re.I | re.S,
    )
    if m:
        data["material"] = data["material"] or _clean(m.group(1))
        data["schedule_date"] = _clean(m.group(2))
        data["qty"] = _num(m.group(3))
        data["uom"] = _clean(m.group(4)).upper()
        data["unit_price"] = _num(m.group(5))
        data["extended_price"] = _num(m.group(6))
    else:
        data["schedule_date"] = grab(r"Schedule Date\s*:?\s*([0-9]{2}-[A-Z]{3}-[0-9]{2})")
        data["qty"] = _num(grab(r"(?:Total Qty|Quantity)\s*:?\s*([0-9,.]+)"))
        data["uom"] = grab(r"\bTON\b", "TON")
        data["unit_price"] = _num(grab(r"Unit Price\s*:?\s*([0-9,.]+)"))
        data["extended_price"] = _num(grab(r"Extended Price\s*:?\s*([0-9,.]+)"))

    data["order_total"] = _num(grab(r"ORDER TOTAL\s*:?\s*([0-9,.]+)"))
    if data["ship_to"]:
        data["to_place"] = data["ship_to"].splitlines()[0].strip()[:60]
    return data
