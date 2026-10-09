""""Robust field extraction for GMDC Delivery Order PDFs."""
import re

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None


def _num(s):
    if s is None:
        return 0.0
    m = re.search(r"-?\\d[\\d,]*(?:\\.\\d+)?", str(s))
    try:
        return float(m.group().replace(",", "")) if m else 0.0
    except Exception:
        return 0.0


def _clean(value):
    return re.sub(r"\\s+", " ", (value or "")).strip(" :\\t")


def _label_value(text, label, stop_labels=()):
    """Find a value after a label whether the PDF puts it on this or next line."""
    labels = ["Customer Number", "Customer No", "Customer Name", "Customer GSTIN",
              "Order Number", "Order Date", "Order Type", "Bill To", "Ship To",
              "State", "HSN Code", "Description of Goods", "Transporter Code",
              "Transporter Name", "ORDER TOTAL", "Total Qty"]
    labels = sorted(set(labels + list(stop_labels)), key=len, reverse=True)
    stop = "|".join(re.escape(x) for x in labels if x.lower() != label.lower())
    pattern = rf"{re.escape(label)}\\s*[:#]?\\s*(.*?)(?=\\s+(?:{stop})\\b|[\\r\\n]+|$)"
    m = re.search(pattern, text, re.I)
    value = _clean(m.group(1)) if m else ""
    if value and value.lower() not in (label.lower(),):
        return value
    # Label and value may be separated by one or more line breaks in extracted text.
    pattern = rf"{re.escape(label)}\\s*[:#]?\\s*[\\r\\n]+\\s*([^\\r\\n]+)"
    m = re.search(pattern, text, re.I)
    return _clean(m.group(1)) if m else ""


def parse_pdf(path):
    """Extract DO fields from GMDC PDF text; avoid confusing customer number and GSTIN."""
    if PdfReader is None:
        raise RuntimeError("pypdf is not installed. Run: pip install pypdf")
    text = "\\n".join((p.extract_text() or "") for p in PdfReader(path).pages)
    text = text.replace("\\u00a0", " ")

    def grab(pattern, default=""):
        m = re.search(pattern, text, re.I | re.M)
        return _clean(m.group(1)) if m else default

    do_no = grab(r"Order Number\\s*[:#]?\\s*([0-9]+)",
                 grab(r"Delivery Order\\s*\\*?([0-9]{8,})\\*?"))
    do_date = grab(r"Order Date\\s*[:#]?\\s*([0-9A-Z-]+)")

    # Capture GSTIN-shaped tokens independently of the PDF's column reading order.
    gstins = re.findall(r"\\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]\\b", text, re.I)
    gstins = [g.upper() for g in gstins]
    customer_gstin = ""
    for gst in gstins:
        if gst != "24AAACG7987P1ZT":
            customer_gstin = gst
            break

    customer_no = _label_value(text, "Customer Number")
    if not customer_no:
        customer_no = _label_value(text, "Customer No")
    # Only accept numeric customer IDs; never accept a GSTIN or another label.
    m = re.search(r"Customer\\s+(?:Number|No)\\s*[:#]?\\s*(?:[\\r\\n]+\\s*)?([0-9]{3,12})\\b", text, re.I)
    if m:
        customer_no = m.group(1)
    if not customer_no.isdigit():
        customer_no = ""

    customer_name = _label_value(text, "Customer Name", ("Customer GSTIN",))
    # PDFs often extract side-by-side columns in a different sequence. Use the
    # text between Customer Name and the next known field as a fallback.
    if not customer_name:
        m = re.search(r"Customer Name\\s*[:#]?\\s*[\\r\\n]+\\s*(.+?)(?=\\s*Customer GSTIN|\\s*Bill To|\\s*Ship To|\\s*State\\b)", text, re.I | re.S)
        if m:
            customer_name = _clean(m.group(1))
    # Reject field labels and numbers accidentally captured as a party name.
    if customer_name and re.search(r"^(Customer GSTIN|Customer Number|\\d{3,})$", customer_name, re.I):
        customer_name = ""

    data = {
        "do_no": do_no,
        "do_date": do_date,
        "customer_no": customer_no,
        "customer_name": customer_name,
        "customer_gstin": customer_gstin or _label_value(text, "Customer GSTIN"),
        "order_type": _label_value(text, "Order Type"),
        "bill_to": _label_value(text, "Bill To", ("Ship To", "State")),
        "ship_to": _label_value(text, "Ship To", ("State", "HSN Code")),
        "state": grab(r"State\\s*:\\s*([A-Z ]+?)\\s+HSN"),
        "hsn": grab(r"HSN Code\\s*:\\s*([0-9]+)"),
        "material": grab(r"Description of Goods\\s*:\\s*(.+?)(?:\\r?\\n|$)"),
        "schedule_date": "",
        "qty": 0.0,
        "uom": "TON",
        "unit_price": 0.0,
        "extended_price": 0.0,
        "transporter_code": _label_value(text, "Transporter Code"),
        "transporter_name": _label_value(text, "Transporter Name"),
        "order_total": _num(grab(r"ORDER TOTAL\\s+([0-9,]+(?:\\.[0-9]+)?)")),
        "from_place": "BHAVNAGAR",
        "to_place": "",
    }

    # GMDC line-item row: description, schedule date, quantity, UOM, unit price, extended price.
    m = re.search(
        r"\\b1\\s+(.+?)\\s+([0-9]{2}-[A-Z]{3}-[0-9]{2})\\s+([0-9,]+(?:\\.[0-9]+)?)\\s+([A-Z]+)\\s+([0-9,]+(?:\\.[0-9]+)?)\\s+([0-9,]+(?:\\.[0-9]+)?)",
        text, re.I | re.S,
    )
    if m:
        data["material"] = data["material"] or _clean(m.group(1))
        data["schedule_date"] = m.group(2).upper()
        data["qty"] = _num(m.group(3))
        data["uom"] = m.group(4).upper()
        data["unit_price"] = _num(m.group(5))
        data["extended_price"] = _num(m.group(6))
    else:
        data["qty"] = _num(grab(r"Total Qty\\s*[: ]+([0-9,]+(?:\\.[0-9]+)?)"))

    if data["ship_to"]:
        data["to_place"] = data["ship_to"].splitlines()[0].strip()[:60]
    return data
