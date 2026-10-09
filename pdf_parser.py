"""PDF parsing for GMDC Delivery Order PDFs."""
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


def parse_pdf(path):
    """Extract Delivery Order fields from the GMDC PDF format."""
    if PdfReader is None:
        raise RuntimeError("pypdf is not installed. Run: pip install pypdf")

    text = "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)

    def grab(pattern, default=""):
        m = re.search(pattern, text, re.I | re.M)
        return m.group(1).strip() if m else default

    data = {
        "do_no": grab(r"Order Number\s+([0-9]+)",
                      grab(r"Delivery Order\s*\*([0-9]+)\*")),
        "do_date": grab(r"Order Date\s+([0-9A-Z-]+)"),
        "customer_no": grab(r"Customer Number\s*[\r\n]+([0-9]+)"),
        "customer_name": grab(
            r"Customer Name\s*[\r\n]+(.+?)\s*[\r\n]+(?:Customer GSTIN|24[A-Z0-9]+)"
        ),
        "customer_gstin": grab(r"Customer GSTIN\s*[\r\n]+([0-9A-Z]+)"),
        "order_type": grab(r"Order Type\s+(.+?)(?:\r?\n|$)"),
        "bill_to": grab(r"Bill To\s*[:\r\n]+(.+?)(?:\r?\n\r?\n|Ship To)"),
        "ship_to": grab(r"Ship To\s*[:\r\n]+(.+?)(?:\r?\n\r?\n|State\s*:)"),
        "state": grab(r"State\s*:\s*([A-Z ]+?)\s+HSN"),
        "hsn": grab(r"HSN Code\s*:\s*([0-9]+)"),
        "material": grab(r"Description of Goods\s*:\s*(.+?)(?:\r?\n|$)"),
        "schedule_date": grab(
            r"\d+\s+BHAVNAGAR.*?\s+([0-9]{2}-[A-Z]{3}-[0-9]{2})\s+31\s+TON", ""
        ),
        "transporter_code": grab(r"Transporter Code\s*:\s*([A-Z0-9]+)"),
        "transporter_name": grab(r"Transporter Name\s*:\s*(.+?)(?:\r?\n|$)"),
        "from_place": "BHAVNAGAR",
        "to_place": "",
    }

    m = re.search(
        r"\n?1\s+(.+?)\s+([0-9]{2}-[A-Z]{3}-[0-9]{2})\s+([0-9.]+)\s+([A-Z]+)\s+([0-9.]+)\s+([0-9.]+)",
        text, re.I,
    )
    if m:
        data["material"] = data["material"] or m.group(1).strip()
        data["schedule_date"] = data["schedule_date"] or m.group(2)
        data["qty"] = _num(m.group(3))
        data["uom"] = m.group(4)
        data["unit_price"] = _num(m.group(5))
        data["extended_price"] = _num(m.group(6))
    else:
        data["qty"] = _num(grab(r"Total Qty:\s*([0-9.]+)"))
        data["uom"] = "TON"
        data["unit_price"] = 0.0
        data["extended_price"] = 0.0

    data["order_total"] = _num(grab(r"ORDER TOTAL\s+([0-9.]+)"))

    # Infer destination from ship_to first line (fallback: state)
    if data["ship_to"]:
        first = data["ship_to"].splitlines()[0].strip()
        data["to_place"] = first[:60]
    return data
