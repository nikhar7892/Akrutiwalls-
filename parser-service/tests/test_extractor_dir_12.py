import tempfile
import unittest
from pathlib import Path

from parser.extractors.dir_12 import extract
from tests import synthetic_pdfs as sp


class TestDir12Extractor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_happy_path_two_directors(self):
        pdf = sp.write_dir_12(self.tmp / "dir12.pdf")
        out = extract(pdf)
        self.assertEqual(out["doc_type"], "DIR_12")
        # SRN-first contract — must populate mca_filing chunk.
        self.assertEqual(out["mca_filing"]["srn"], sp.SAMPLE_SRN_DIR_12)
        self.assertEqual(out["mca_filing"]["form_type"], "DIR-12")
        # Purpose value MUST come from the report's controlled vocabulary.
        self.assertEqual(out["metadata"]["purpose_of_filing"], "Appointment")
        # Repeating-section iteration: assert ≥ 2 rows.
        directors = out["directors_kmp"]
        self.assertEqual(len(directors), 2, "DIR-12 must iterate per-director blocks")
        dins = sorted(d["din"] for d in directors)
        self.assertEqual(dins, sorted([sp.SAMPLE_DIN_1, sp.SAMPLE_DIN_2]))
        # Designation enum verbatim from report §9.D.
        designations = sorted(d["designation"] for d in directors)
        self.assertEqual(designations, sorted(["Director", "Managing Director"]))
        # Categories from §9.B.
        for d in directors:
            self.assertEqual(d["category"], "Promoter")

    def test_off_vocab_purpose_logs_soft_warn(self):
        # Build a DIR-12 with an off-vocab purpose; must surface a warning and
        # preserve the raw string in metadata (no silent normalisation).
        pdf = self.tmp / "dir12_offvocab.pdf"
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(pdf))
        for i, line in enumerate([
            "Ministry of Corporate Affairs",
            "Form No. DIR-12",
            f"CIN: {sp.SAMPLE_CIN}",
            f"SRN: {sp.SAMPLE_SRN_DIR_12}",
            "Purpose of filing: Something invented not in the spec",
            "Particulars of Director [1]",
            f"DIN: {sp.SAMPLE_DIN_1}",
            "Name: JOHN SMITH",
            "Designation: Director",
            "Date of appointment: 05/04/2018",
        ]):
            c.drawString(60, 800 - i * 14, line)
        c.save()
        out = extract(pdf)
        self.assertIsNone(out["metadata"]["purpose_of_filing"])
        self.assertEqual(
            out["metadata"]["purpose_of_filing_raw"],
            "Something invented not in the spec",
        )
        self.assertTrue(any("not in controlled vocabulary" in w for w in out["warnings"]))


if __name__ == "__main__":
    unittest.main()
