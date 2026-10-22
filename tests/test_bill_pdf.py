import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from pdf_render import generate_bill_pdf


class BillPdfRegressionTests(unittest.TestCase):
    def render_bill(self, basis):
        bill = {
            "bill_no": "TEST-001",
            "bill_date": "22/10/2026",
            "bill_type": "MATERIAL",
            "customer_name": "SAMPLE CUSTOMER",
            "customer_gstin": "24ABCDE1234F1Z5",
            "total_qty": 9 if basis == "Both Less" else (80 if basis == "Despatch" else 89),
            "rate_per_ton": 2100,
            "subtotal": 18900 if basis == "Both Less" else (168000 if basis == "Despatch" else 186900),
            "cgst": 0,
            "sgst": 0,
            "igst": 0,
            "total": 18900 if basis == "Both Less" else (168000 if basis == "Despatch" else 186900),
            "round_off": 0,
            "weight_basis": basis,
            "item_name": "LIGNITE",
            "mines_name": "MADHANA",
            "do_no": "DO-100",
        }
        builties = [{
            "date": "22/10/2026",
            "builty_no": "B-001",
            "do_no": "DO-100",
            "truck_no": "GJ12AB1234",
            "from_place": "MADHANA",
            "despatch_weight": 80,
            "receipt_weight": 89,
            "qty": 80,
            "sale_rate": 1700,
            "sale_amount": 136000,
        }]
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "bill.pdf"
        generate_bill_pdf(out, {"name": "RADHE RADHE DEVELOPER"}, bill, builties)
        self.assertTrue(out.exists())
        self.assertGreater(out.stat().st_size, 1000)
        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(out)).pages)
        return text

    def test_bill_pdf_prints_entered_rate_and_line_amount(self):
        text = self.render_bill("Both Less")
        self.assertIn("Rate Rs.", text)
        self.assertIn("Amount Rs.", text)
        self.assertIn("2,100.00", text)
        self.assertIn("18,900.00", text)
        self.assertIn("Rate / TON", text)

    def test_despatch_basis_amount_matches_rate(self):
        text = self.render_bill("Despatch")
        self.assertIn("168,000.00", text)
        self.assertIn("2,100.00", text)

    def test_receipt_basis_amount_matches_rate(self):
        text = self.render_bill("Receipt")
        self.assertIn("186,900.00", text)
        self.assertIn("2,100.00", text)


if __name__ == "__main__":
    unittest.main()
