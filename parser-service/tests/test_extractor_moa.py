import tempfile
import unittest
from pathlib import Path

from parser.extractors.moa import extract
from tests import synthetic_pdfs as sp


class TestMoaExtractor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_happy_path(self):
        pdf = sp.write_moa(self.tmp / "moa.pdf")
        out = extract(pdf)
        self.assertEqual(out["doc_type"], "MOA")
        self.assertEqual(out["company"]["legal_name"], sp.SAMPLE_LEGAL_NAME)
        self.assertEqual(out["company"]["authorised_capital"], sp.SAMPLE_AUTHORISED_CAPITAL)

        clauses = {c["clause_roman"]: c for c in out["moa_clauses"]}
        for r in ("I", "II", "III", "IV", "V", "VI"):
            self.assertIn(r, clauses, f"MoA clause {r} missing")

        # Capital sub_clauses on V.
        v = clauses["V"]
        self.assertIsNotNone(v.get("sub_clauses"))
        self.assertEqual(v["sub_clauses"]["number_of_shares"], 100000)
        self.assertEqual(v["sub_clauses"]["face_value_rupees"], 10)
        self.assertEqual(v["sub_clauses"]["share_class"], "equity")

        # Objects sub_clauses on III with main + ancillary populated.
        iii_subs = clauses["III"].get("sub_clauses") or {}
        self.assertTrue(iii_subs.get("main"))
        self.assertTrue(iii_subs.get("ancillary"))

        # Registered-office state surfaced in metadata.
        self.assertEqual(out["metadata"]["registered_office_state"], "Maharashtra")
        self.assertEqual(out["metadata"]["liability_type"], "limited by shares")

        # Subscribers parsed from the page-2 table (≥1 row).
        self.assertGreaterEqual(out["metadata"]["subscribers_count"], 2)

    def test_negative_no_clauses(self):
        pdf = self.tmp / "moa_empty.pdf"
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(pdf))
        c.drawString(60, 800, "MEMORANDUM OF ASSOCIATION OF Empty Co")
        c.save()
        out = extract(pdf)
        self.assertEqual(out["moa_clauses"], [])


if __name__ == "__main__":
    unittest.main()
