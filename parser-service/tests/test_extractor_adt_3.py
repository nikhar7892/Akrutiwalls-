import tempfile
import unittest
from pathlib import Path

from parser.extractors.adt_3 import extract
from parser.identifiers import is_valid_srn
from tests import synthetic_pdfs as sp


class TestAdt3Extractor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_happy_path(self):
        pdf = sp.write_adt_3(self.tmp / "adt3.pdf")
        out = extract(pdf)
        self.assertEqual(out["doc_type"], "ADT_3")
        self.assertEqual(out["mca_filing"]["srn"], sp.SAMPLE_SRN_ADT_3)
        self.assertEqual(out["mca_filing"]["form_type"], "ADT-3")
        # The auditor row carries BOTH the ADT-1 link and the ADT-3 SRN.
        self.assertEqual(len(out["auditors"]), 1)
        a = out["auditors"][0]
        self.assertEqual(a["firm_registration_no"], sp.SAMPLE_FRN)
        self.assertEqual(a["frn_or_membership_no"], sp.SAMPLE_FRN)
        self.assertEqual(a["adt1_srn"], sp.SAMPLE_SRN_ADT_1)
        self.assertEqual(a["adt3_srn"], sp.SAMPLE_SRN_ADT_3)
        self.assertEqual(a["resignation_date"], "2024-03-15")
        self.assertIn("pre-occupied", (a["resignation_reason"] or "").lower())

    def test_missing_adt1_srn_doesnt_crash(self):
        pdf = self.tmp / "adt3_no_link.pdf"
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(pdf))
        for i, line in enumerate([
            "Ministry of Corporate Affairs",
            "Form No. ADT-3",
            f"CIN: {sp.SAMPLE_CIN}",
            f"SRN: {sp.SAMPLE_SRN_ADT_3}",
            "Category of auditor: Firm",
            f"Firm Registration Number: {sp.SAMPLE_FRN}",
            "Date of resignation: 15/03/2024",
        ]):
            c.drawString(60, 800 - i * 14, line)
        c.save()
        out = extract(pdf)
        self.assertEqual(out["auditors"][0]["adt3_srn"], sp.SAMPLE_SRN_ADT_3)
        self.assertIsNone(out["auditors"][0]["adt1_srn"])
        # Doc-self SRN still passes the Stage 1 format check.
        self.assertTrue(is_valid_srn(out["mca_filing"]["srn"]))


if __name__ == "__main__":
    unittest.main()
