import tempfile
import unittest
from pathlib import Path

from parser.extractors.mca_master_data import extract
from tests import synthetic_pdfs as sp


class TestMcaMasterDataExtractor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_happy_path(self):
        pdf = sp.write_mca_master_data(self.tmp / "mca.pdf")
        out = extract(pdf)
        self.assertEqual(out["doc_type"], "MCA_MASTER_DATA")
        c = out["company"]
        self.assertEqual(c["cin"], sp.SAMPLE_CIN)
        self.assertEqual(c["legal_name"], sp.SAMPLE_LEGAL_NAME)
        self.assertEqual(c["roc_jurisdiction"], "RoC-Mumbai")
        self.assertEqual(c["company_status"], "Active")
        self.assertEqual(c["listing_status"], "Unlisted")
        self.assertEqual(c["authorised_capital"], 1_000_000)
        self.assertEqual(c["paid_up_capital"], 100_000)
        self.assertEqual(c["last_agm_date"], "2024-09-30")
        self.assertEqual(c["last_balance_sheet_date"], "2024-03-31")
        self.assertEqual(c["date_of_incorporation"], "2018-04-05")

        # Directors table → 2 entries (DINs valid).
        directors = out["directors_kmp"]
        self.assertEqual(len(directors), 2)
        dins = sorted(d["din"] for d in directors)
        self.assertEqual(dins, sorted([sp.SAMPLE_DIN_1, sp.SAMPLE_DIN_2]))
        for d in directors:
            self.assertEqual(d["din_or_pan"], d["din"])

    def test_status_not_active_flagged(self):
        pdf = self.tmp / "mca_inactive.pdf"
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(pdf))
        for i, line in enumerate([
            "Ministry of Corporate Affairs",
            "Company/LLP Master Data",
            f"CIN: {sp.SAMPLE_CIN}",
            f"Company Name: {sp.SAMPLE_LEGAL_NAME}",
            "Company Status: Strike Off",
        ]):
            c.drawString(60, 800 - i * 14, line)
        c.save()
        out = extract(pdf)
        self.assertEqual(out["company"]["company_status"], "Strike Off")
        self.assertFalse(out["metadata"]["is_active"])


if __name__ == "__main__":
    unittest.main()
