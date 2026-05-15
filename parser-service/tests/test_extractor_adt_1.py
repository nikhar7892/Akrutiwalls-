import tempfile
import unittest
from pathlib import Path

from parser.extractors.adt_1 import extract
from tests import synthetic_pdfs as sp


class TestAdt1Extractor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_happy_path_two_joint_auditors(self):
        pdf = sp.write_adt_1(self.tmp / "adt1.pdf")
        out = extract(pdf)
        self.assertEqual(out["doc_type"], "ADT_1")
        self.assertEqual(out["mca_filing"]["srn"], sp.SAMPLE_SRN_ADT_1)
        self.assertEqual(out["mca_filing"]["form_type"], "ADT-1")
        # Nature of appointment enum verbatim from §11.B field 3(b).
        self.assertEqual(out["metadata"]["nature_of_appointment"], "Appointment in AGM")
        # Joint auditors → ≥ 2 rows.
        auditors = out["auditors"]
        self.assertEqual(len(auditors), 2, "ADT-1 must iterate per-auditor blocks")
        # First (Firm) has FRN per §11.B I(d).
        firm = next(a for a in auditors if a["category"] == "Firm")
        self.assertEqual(firm["firm_registration_no"], sp.SAMPLE_FRN)
        self.assertEqual(firm["frn_or_membership_no"], sp.SAMPLE_FRN)
        # Second (Individual) — Membership No used as identifier.
        ind = next(a for a in auditors if a["category"] == "Individual")
        self.assertEqual(ind["icai_membership_no"], "098765")
        self.assertEqual(ind["frn_or_membership_no"], "098765")

    def test_off_vocab_nature_logs_soft_warn(self):
        pdf = self.tmp / "adt1_offvocab.pdf"
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(pdf))
        for i, line in enumerate([
            "Ministry of Corporate Affairs",
            "Form ADT-1",
            f"CIN: {sp.SAMPLE_CIN}",
            f"SRN: {sp.SAMPLE_SRN_ADT_1}",
            "Nature of appointment: Some Other Path",
            "Auditor [1]",
            "Category: Firm",
            f"Firm Registration Number: {sp.SAMPLE_FRN}",
            "Name: ACME LLP",
            "Period of account from: 01/04/2023",
        ]):
            c.drawString(60, 800 - i * 14, line)
        c.save()
        out = extract(pdf)
        self.assertIsNone(out["metadata"]["nature_of_appointment"])
        self.assertEqual(out["metadata"]["nature_of_appointment_raw"], "Some Other Path")
        self.assertTrue(any("not in controlled vocabulary" in w for w in out["warnings"]))


if __name__ == "__main__":
    unittest.main()
