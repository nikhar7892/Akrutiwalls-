import tempfile
import unittest
from pathlib import Path

from parser.extractors.pan_card import extract
from tests import synthetic_pdfs as sp


class TestPanCardExtractor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_happy_path(self):
        pdf = sp.write_pan_card(self.tmp / "pan.pdf")
        out = extract(pdf)
        self.assertEqual(out["doc_type"], "PAN_CARD")
        c = out["company"]
        self.assertEqual(c["pan"], sp.SAMPLE_PAN)
        self.assertEqual(c["legal_name"], sp.SAMPLE_LEGAL_NAME)
        self.assertEqual(c["date_of_incorporation"], "2018-04-05")

    def test_non_company_pan_skipped(self):
        # 4th char 'F' (Firm) — must not be picked up by the company-PAN regex.
        pdf = self.tmp / "pan_firm.pdf"
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(pdf))
        for i, line in enumerate([
            "INCOME TAX DEPARTMENT — GOVT. OF INDIA",
            "Permanent Account Number Card",
            "PAN: AAPFU0939F",
            "Name: Some Firm",
            "Date of Incorporation: 05/04/2018",
        ]):
            c.drawString(60, 800 - i * 14, line)
        c.save()
        out = extract(pdf)
        self.assertIsNone(out["company"]["pan"])


if __name__ == "__main__":
    unittest.main()
