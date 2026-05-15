import tempfile
import unittest
from pathlib import Path

from parser.extractors.aoa import extract
from tests import synthetic_pdfs as sp


class TestAoaExtractor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_happy_path(self):
        pdf = sp.write_aoa(self.tmp / "aoa.pdf")
        out = extract(pdf)
        self.assertEqual(out["doc_type"], "AOA")
        self.assertEqual(out["company"]["legal_name"], sp.SAMPLE_LEGAL_NAME)
        # At least the headings present in our synthetic AoA must produce clauses.
        clauses = out["aoa_clauses"]
        articles = {c["article_no"] for c in clauses}
        for required in ("I", "II", "III", "XIX", "XXIII"):
            self.assertIn(required, articles)
        # 'Seal optional?' flag should be set because clause XIX says "Seal ... optional".
        self.assertTrue(out["metadata"]["flags"]["seal_optional"])
        # Subscription block extracted.
        self.assertIn("In witness whereof", out["metadata"]["subscription_text"] or "")

    def test_no_articles_returns_empty_clauses(self):
        pdf = self.tmp / "aoa_empty.pdf"
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(pdf))
        c.drawString(60, 800, "ARTICLES OF ASSOCIATION OF Empty Co")
        c.save()
        out = extract(pdf)
        self.assertEqual(out["aoa_clauses"], [])


if __name__ == "__main__":
    unittest.main()
