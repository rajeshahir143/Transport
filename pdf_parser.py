"""GMDC DO PDF parser with robust label/value extraction."""
import re
try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

def _clean(value):
    return re.sub(r"\\s+", " ", (value or "")).strip(" :\\t")

def _num(value):
    m = re.search(r"-?\\d[\\d,]*(?:\\.\\d+)?", str(value or ""))
    return float(m.group().replace(",", "")) if m else 0.0

def parse_pdf(path):
    if PdfReader is None:
        raise RuntimeError("Install pypdf: pip install pypdf")
    text = "\\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
    text = text.replace("\\u00a0", " ")
    def grab(pattern, default=""):
        m = re.search(pattern, text, re.I | re.M)
        return _clean(m.group(1)) if m else default

    # Customer fields share a line in many GMDC PDF text extractions.
    customer_no = grab(r"Customer Number\\s+([0-9]{3,12})")
    customer_name = grab(r"Customer Name\\s+(.+?)(?=\\s+Customer GSTIN\\b|\\s+Order Date\\b|\\r?\\n|$)")
    customer_gstin = grab(r"Customer GSTIN\\s+([0-9A-Z]{15})")
    if customer_gstin.upper() == "24AAACG7987P1ZT":
        matches = re.findall(r"\\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]\\b", text, re.I)
        customer_gstin = next((g.upper() for g in matches if g.upper() != "24AAACG7987P1ZT"), "")
    order_type = grab(r"Order Type\\s+(.+?)(?=\\r?\\n|$)")
    if "HOD-BHAV-Lignte" in text and re.search(r"Order Type.*?HOD-BHAV-Lignte.*?Order E", text, re.I | re.S):
        order_type = "HOD-BHAV-Lignte Order E"
    row = re.search(r"\\b1\\s+(.+?)\\s+([0-9]{2}-[A-Z]{3}-[0-9]{2})\\s+([0-9,]+(?:\\.[0-9]+)?)\\s+([A-Z]+)\\s+([0-9,]+(?:\\.[0-9]+)?)\\s+([0-9,]+(?:\\.[0-9]+)?)", text, re.I | re.S)
    data = {
        "do_no": grab(r"Order Number\\s+([0-9]+)", grab(r"Delivery Order\\s*\\*?([0-9]{8,})")),
        "do_date": grab(r"Order Date\\s+([0-9A-Z-]+)"),
        "customer_no": customer_no, "customer_name": customer_name,
        "customer_gstin": customer_gstin.upper(), "order_type": order_type,
        "bill_to": "", "ship_to": "",
        "state": grab(r"State\\s*:\\s*([A-Z ]+?)\\s+HSN"),
        "hsn": grab(r"HSN Code\\s*:\\s*([0-9]+)"),
        "material": grab(r"Description of Goods\\s*:\\s*(.+?)(?:\\r?\\n|$)"),
        "schedule_date": "", "qty": 0.0, "uom": "TON",
        "unit_price": 0.0, "extended_price": 0.0,
        "transporter_code": grab(r"Transporter Code\\s*:\\s*([A-Z0-9]+)"),
        "transporter_name": grab(r"Transporter Name\\s*:\\s*(.+?)(?:\\r?\\n|$)"),
        "order_total": _num(grab(r"ORDER TOTAL\\s+([0-9,]+(?:\\.[0-9]+)?)")),
        "from_place": "BHAVNAGAR", "to_place": ""
    }
    if row:
        data.update(material=data["material"] or _clean(row.group(1)),
                    schedule_date=row.group(2).upper(), qty=_num(row.group(3)),
                    uom=row.group(4).upper(), unit_price=_num(row.group(5)),
                    extended_price=_num(row.group(6)))
    else:
        data["qty"] = _num(grab(r"Total Qty\\s*:\\s*([0-9,]+(?:\\.[0-9]+)?)"))
    return data
