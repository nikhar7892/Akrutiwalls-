import tempfile
import unittest
from pathlib import Path

from parser.extractors.udyam import extract
from tests import synthetic_pdfs as sp


class TestUdyamExtractor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_happy_path(self):
        pdf = sp.write_udyam(self.tmp / "udyam.pdf")
        out = extract(pdf)
        self.assertEqual(out["doc_type"], "UDYAM")
        regs = out["registrations"]
        self.assertEqual(len(regs), 1)
        r = regs[0]
        self.assertEqual(r["type"], "UDYAM")
        self.assertEqual(r["udyam_registration_number"], sp.SAMPLE_UDYAM)
        self.assertEqual(r["udyam_enterprise_type"], "Micro")
        self.assertEqual(r["udyam_date_of_registration"], "2020-05-12")
        self.assertEqual(r["udyam_date_of_commencement"], "2018-05-06")
        self.assertIn("62", r["nic_codes"])

        c = out["company"]
        self.assertEqual(c["pan"], sp.SAMPLE_PAN)
        self.assertEqual(c["legal_name"], sp.SAMPLE_LEGAL_NAME)

        m = out["metadata"]
        self.assertEqual(m["major_activity"], "Services")
        self.assertEqual(m["owner_aadhaar_last4"], "1234")
        # Linked GSTIN found.
        self.assertIn(sp.SAMPLE_GSTIN, m["linked_gstins"])

    def test_no_urn_no_registration(self):
        pdf = self.tmp / "udyam_empty.pdf"
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(pdf))
        c.drawString(60, 800, "Government of India — Ministry of MSME")
        c.drawString(60, 780, "Udyam Registration Certificate (placeholder)")
        c.save()
        out = extract(pdf)
        self.assertEqual(out["registrations"], [])


if __name__ == "__main__":
    unittest.main()
