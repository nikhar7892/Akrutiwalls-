import tempfile
import unittest
from pathlib import Path

from parser.extractors.mgt_14 import extract
from tests import synthetic_pdfs as sp


class TestMgt14Extractor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_happy_path_two_resolutions(self):
        pdf = sp.write_mgt_14(self.tmp / "mgt14.pdf")
        out = extract(pdf)
        self.assertEqual(out["doc_type"], "MGT_14")
        self.assertEqual(out["mca_filing"]["srn"], sp.SAMPLE_SRN_MGT_14)
        self.assertEqual(out["mca_filing"]["form_type"], "MGT-14")
        resolutions = out["resolutions"]
        self.assertEqual(len(resolutions), 2, "MGT-14 must iterate per-resolution blocks")
        # Type enum verbatim from §10.B.
        types_seen = sorted(r["resolution_type"] for r in resolutions)
        self.assertEqual(types_seen, sorted(["Special", "Board"]))
        # Purpose enum verbatim from §10.B.
        purposes = sorted(r["purpose"] for r in resolutions)
        self.assertEqual(purposes, sorted(["Alteration in Articles", "Borrowing limits"]))
        # Section regex 'Section\s+(\d+)(?:\(([0-9a-z]+)\))?' per §10.D.
        # The report's regex captures ONE sub-section group — anything nested
        # beyond that (e.g. trailing '(c)' in '180(1)(c)') is not captured.
        sections = sorted(r["section_under"] for r in resolutions)
        self.assertIn("s.14", sections)
        self.assertIn("s.180(1)", sections)

    def test_off_vocab_resolution_type_logs_soft_warn(self):
        pdf = self.tmp / "mgt14_offvocab.pdf"
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(pdf))
        for i, line in enumerate([
            "Ministry of Corporate Affairs",
            "Form No. MGT-14",
            f"CIN: {sp.SAMPLE_CIN}",
            f"SRN: {sp.SAMPLE_SRN_MGT_14}",
            "Resolution [1]",
            "Type: Special Magic Resolution",
            "Purpose: Buy-back",
            "Section 68",
            "Date of resolution: 30/09/2023",
        ]):
            c.drawString(60, 800 - i * 14, line)
        c.save()
        out = extract(pdf)
        # Off-vocab type raw preserved.
        self.assertEqual(out["resolutions"][0]["resolution_type"], "Special Magic Resolution")
        self.assertTrue(any("not in controlled vocabulary" in w for w in out["warnings"]))


if __name__ == "__main__":
    unittest.main()
