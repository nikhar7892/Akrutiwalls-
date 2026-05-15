import tempfile
import unittest
from pathlib import Path

from parser.extractors.gst_reg_06 import extract
from tests import synthetic_pdfs as sp


class TestGstReg06Extractor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_happy_path(self):
        pdf = sp.write_gst_reg_06(self.tmp / "gst.pdf")
        out = extract(pdf)
        self.assertEqual(out["doc_type"], "GST_REG_06")
        regs = out["registrations"]
        self.assertEqual(len(regs), 1)
        r = regs[0]
        self.assertEqual(r["type"], "GST")
        self.assertEqual(r["gstin"], sp.SAMPLE_GSTIN)
        self.assertEqual(r["gst_legal_name"], sp.SAMPLE_LEGAL_NAME)
        self.assertEqual(r["constitution_of_business"], "Private Limited Company")
        self.assertEqual(r["type_of_registration"], "Regular")
        self.assertEqual(r["date_of_liability"], "2018-05-06")
        # Annexure A — additional places of business → 2 entries from synthetic table.
        self.assertGreaterEqual(len(r["additional_places_of_business"] or []), 2)
        # PAN derived from GSTIN[3:13] = SAMPLE_PAN.
        self.assertEqual(out["company"]["pan"], sp.SAMPLE_PAN)
        # Date-of-approval anchored on note line.
        self.assertEqual(out["metadata"]["date_of_approval"], "2018-05-06")

    def test_invalid_checksum_drops_gstin(self):
        # Build a doc with a GSTIN whose final char is wrong.
        pdf = self.tmp / "gst_bad.pdf"
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(pdf))
        for i, line in enumerate([
            "Form GST REG-06 [See Rule 10(1)] Registration Certificate",
            "Registration Number: 27AAACD1234E1Z0",   # wrong check digit
            f"1. Legal Name: {sp.SAMPLE_LEGAL_NAME}",
        ]):
            c.drawString(60, 800 - i * 14, line)
        c.save()
        out = extract(pdf)
        self.assertEqual(out["registrations"], [])
        self.assertTrue(any("Luhn-mod-36" in w for w in out["warnings"]))


if __name__ == "__main__":
    unittest.main()
