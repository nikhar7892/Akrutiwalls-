import tempfile
import unittest
from pathlib import Path

from parser.extractors.tan_letter import extract
from tests import synthetic_pdfs as sp


class TestTanLetterExtractor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_happy_path(self):
        pdf = sp.write_tan_letter(self.tmp / "tan.pdf")
        out = extract(pdf)
        self.assertEqual(out["doc_type"], "TAN_LETTER")
        c = out["company"]
        self.assertEqual(c["tan"], sp.SAMPLE_TAN)
        self.assertEqual(c["pan"], sp.SAMPLE_PAN)
        self.assertEqual(c["legal_name"], sp.SAMPLE_LEGAL_NAME)
        m = out["metadata"]
        self.assertEqual(m["date_of_allotment"], "2018-05-10")
        self.assertEqual(m["category"], "Company")
        self.assertEqual(m["form_49b_acknowledgement"], "12345678901234")

    def test_bad_tan_format_skipped(self):
        pdf = self.tmp / "tan_bad.pdf"
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(pdf))
        for i, line in enumerate([
            "Income Tax Department — Government of India",
            "Tax Deduction Account Number (TAN)",
            "TAN: BLR12345AB",   # malformed: 3 letters + 5 digits + 2 letters
        ]):
            c.drawString(60, 800 - i * 14, line)
        c.save()
        out = extract(pdf)
        self.assertIsNone(out["company"]["tan"])


if __name__ == "__main__":
    unittest.main()
