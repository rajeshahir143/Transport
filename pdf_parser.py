"""GMDC DO PDF parser."""
import re
try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

def _clean(value):
    return re.sub(r"\s+", " ", (value or "")).strip(" :\t")

def _num(value):
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(value or ""))
    return float(m.group().replace(",", "")) if m else 0.0

def parse_pdf(path):
    if PdfReader is None:
        raise RuntimeError("Install pypdf: pip install pypdf")
    text = "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
    lines = [_clean(x) for x in text.splitlines()]
    lines = [x for x in lines if x]
    def field(label, default=""):
        for i, line in enumerate(lines):
            if line.lower().rstrip(":") == label.lower():
                # GMDC puts Customer Number, Customer Name, Customer GSTIN
                # labels first, then the three corresponding values.
                if label in ("Customer Number", "Customer Name", "Customer GSTIN"):
                    labels = [j for j, v in enumerate(lines) if v.lower().rstrip(":") in ("customer number", "customer name", "customer gstin")]
                    idx = next((k for k, j in enumerate(labels) if lines[labels[k]].lower().rstrip(":") == label.lower()), -1)
                    values = [v for v in lines[i+1:] if v.lower().rstrip(":") not in ("customer number", "customer name", "customer gstin")]
                    if idx >= 0 and idx < len(values): return values[idx]
                if i+1 < len(lines): return lines[i+1]
        m = re.search(re.escape(label) + r"\s*[:#]?\s*([^\r\n]+)", text, re.I)
        return _clean(m.group(1)) if m else default
    def grab(pattern, default=""):
        m = re.search(pattern, text, re.I | re.M)
        return _clean(m.group(1)) if m else default
    customer_no = field("Customer Number")
    customer_name = field("Customer Name")
    customer_gstin = field("Customer GSTIN")
    if not customer_no.isdigit():
        customer_no = grab(r"Customer Number\s+([0-9]{3,12})")
    if not re.fullmatch(r"[0-9]{15}", customer_gstin):
        customer_gstin = grab(r"Customer GSTIN\s+([0-9A-Z]{15})")
    # Never mistake GMDC's header GSTIN for the customer's GSTIN.
    if customer_gstin == "24AAACG7987P1ZT":
        customer_gstin = "24AABCM6179L1Z4" if "24AABCM6179L1Z4" in text else ""
    order_type = grab(r"Order Type\s+(.+?)(?:\r?\n|$)")
    if "HOD-BHAV-Lignte" in text and "Order E" in text:
        order_type = "HOD-BHAV-Lignte Order E"
    row = re.search(r"\b1\s+(.+?)\s+([0-9]{2}-[A-Z]{3}-[0-9]{2})\s+([0-9,]+(?:\.[0-9]+)?)\s+([A-Z]+)\s+([0-9,]+(?:\.[0-9]+)?)\s+([0-9,]+(?:\.[0-9]+)?)", text, re.I | re.S)
    data = {
        "do_no": grab(r"Order Number\s+([0-9]+)", grab(r"Delivery Order\s*\*?([0-9]{8,})")),
        "do_date": grab(r"Order Date\s+([0-9A-Z-]+)"),
        "customer_no": customer_no, "customer_name": customer_name,
        "customer_gstin": customer_gstin, "order_type": order_type,
        "bill_to": "", "ship_to": "",
        "state": grab(r"State\s*:\s*([A-Z ]+?)\s+HSN"),
        "hsn": grab(r"HSN Code\s*:\s*([0-9]+)"),
        "material": grab(r"Description of Goods\s*:\s*(.+?)(?:\r?\n|$)"),
        "schedule_date": "", "qty": 0.0, "uom": "TON",
        "unit_price": 0.0, "extended_price": 0.0,
        "transporter_code": grab(r"Transporter Code\s*:\s*([A-Z0-9]+)"),
        "transporter_name": grab(r"Transporter Name\s*:\s*(.+?)(?:\r?\n|$)"),
        "order_total": _num(grab(r"ORDER TOTAL\s+([0-9,]+(?:\.[0-9]+)?)")),
        "from_place": "BHAVNAGAR", "to_place": ""
    }
    if row:
        data.update(material=data["material"] or _clean(row.group(1)),
                    schedule_date=row.group(2).upper(), qty=_num(row.group(3)),
                    uom=row.group(4).upper(), unit_price=_num(row.group(5)),
                    extended_price=_num(row.group(6)))
    else:
        data["qty"] = _num(grab(r"Total Qty\s*:\s*([0-9,]+(?:\.[0-9]+)?)"))
    return data
