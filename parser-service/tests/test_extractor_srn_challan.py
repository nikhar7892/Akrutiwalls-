import tempfile
import unittest
from pathlib import Path

from parser.extractors.srn_challan import extract
from tests import synthetic_pdfs as sp


class TestSrnChallanExtractor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_happy_path(self):
        pdf = sp.write_srn_challan(self.tmp / "challan.pdf")
        out = extract(pdf)
        self.assertEqual(out["doc_type"], "SRN_CHALLAN")
        f = out["mca_filing"]
        self.assertEqual(f["srn"], sp.SAMPLE_SRN_CHALLAN)
        # form_type normalised from 'Form DIR-12' → 'DIR-12'.
        self.assertEqual(f["form_type"], "DIR-12")
        self.assertEqual(f["payment_status"], "Paid")
        self.assertEqual(f["payment_mode"], "Net Banking")
        self.assertEqual(out["company"]["cin"], sp.SAMPLE_CIN)

    def test_missing_srn_returns_none(self):
        pdf = self.tmp / "challan_no_srn.pdf"
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(pdf))
        for i, line in enumerate([
            "Ministry of Corporate Affairs — Government of India",
            "Service Request Receipt",
            "Service Description: Form DIR-12",
        ]):
            c.drawString(60, 800 - i * 14, line)
        c.save()
        out = extract(pdf)
        self.assertIsNone(out["mca_filing"]["srn"])


if __name__ == "__main__":
    unittest.main()
