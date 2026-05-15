import tempfile
import unittest
from pathlib import Path

from parser.extractors.dpt_3 import extract
from parser.vocab import DPT3_RULE_2_1_C_SUBCLAUSES
from tests import synthetic_pdfs as sp


class TestDpt3Extractor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_happy_path_with_rule_2_1_c_iteration(self):
        pdf = sp.write_dpt_3(self.tmp / "dpt3.pdf")
        out = extract(pdf)
        self.assertEqual(out["doc_type"], "DPT_3")
        self.assertEqual(out["mca_filing"]["srn"], sp.SAMPLE_SRN_DPT_3)
        # Purpose enum verbatim from §15.B field 3.
        self.assertEqual(out["metadata"]["purpose_of_filing"], "Annual Return of deposits")
        # Deposits row.
        deposits = out["deposits"]
        self.assertEqual(len(deposits), 1)
        d = deposits[0]
        self.assertEqual(d["financial_year"], "2023-24")
        self.assertEqual(d["dpt3_srn"], sp.SAMPLE_SRN_DPT_3)
        # Rule 2(1)(c) sub-clauses (i)..(xiii) iterated per §15.B field 12.
        breakdown = out["metadata"]["rule_2_1_c_breakdown"]
        self.assertGreaterEqual(len(breakdown), 13)
        expected_keys = [k for k, _ in DPT3_RULE_2_1_C_SUBCLAUSES]
        actual_keys = [row["sub_clause"] for row in breakdown[: len(expected_keys)]]
        self.assertEqual(actual_keys, expected_keys, "Sub-clauses must preserve i..xiii order")

    def test_off_vocab_purpose_logs_soft_warn(self):
        pdf = self.tmp / "dpt3_offvocab.pdf"
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(pdf))
        for i, line in enumerate([
            "Form No. DPT-3",
            f"CIN: {sp.SAMPLE_CIN}",
            f"SRN: {sp.SAMPLE_SRN_DPT_3}",
            "Purpose of filing: Some Other Reason",
            "Period for which return is filed: 2023-24",
        ]):
            c.drawString(60, 800 - i * 14, line)
        c.save()
        out = extract(pdf)
        self.assertIsNone(out["metadata"]["purpose_of_filing"])
        self.assertEqual(out["metadata"]["purpose_of_filing_raw"], "Some Other Reason")
        self.assertTrue(any("not in controlled vocabulary" in w for w in out["warnings"]))


if __name__ == "__main__":
    unittest.main()
