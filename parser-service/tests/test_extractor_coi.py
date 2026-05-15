import tempfile
import unittest
from pathlib import Path

from parser.extractors.coi import extract
from tests import synthetic_pdfs as sp


class TestCoiExtractor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_happy_path(self):
        pdf = sp.write_coi(self.tmp / "coi.pdf")
        out = extract(pdf)
        self.assertEqual(out["doc_type"], "COI")
        c = out["company"]
        self.assertEqual(c["cin"], sp.SAMPLE_CIN)
        self.assertEqual(c["pan"], sp.SAMPLE_PAN)
        self.assertEqual(c["legal_name"], sp.SAMPLE_LEGAL_NAME)
        # Words-date "FIFTH day of APRIL two thousand eighteen" → 2018-04-05.
        self.assertEqual(c["date_of_incorporation"], "2018-04-05")
        self.assertEqual(out["metadata"]["constitution"], "limited by shares")

    def test_no_cin_in_document_returns_none(self):
        # Negative path: COI body that omits the CIN line entirely. The PAN
        # must still extract; CIN must come back as None with no false warning.
        pdf = self.tmp / "coi_no_cin.pdf"
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(pdf))
        for i, line in enumerate([
            "Certificate of Incorporation [Pursuant to sub-section (2) of section 7 of the Companies Act, 2013 (18 of 2013) and rule 18 of the Companies (Incorporation) Rules, 2014]",
            f"I hereby certify that {sp.SAMPLE_LEGAL_NAME} is incorporated on this FIFTH day of APRIL two thousand eighteen under the Companies Act, 2013.",
            f"The Permanent Account Number (PAN) of the company is {sp.SAMPLE_PAN}.",
        ]):
            c.drawString(60, 800 - i * 14, line)
        c.save()
        out = extract(pdf)
        self.assertIsNone(out["company"]["cin"])
        self.assertEqual(out["company"]["pan"], sp.SAMPLE_PAN)


if __name__ == "__main__":
    unittest.main()
