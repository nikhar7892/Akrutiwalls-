import tempfile
import unittest
from pathlib import Path

from parser.classifier import DocType, classify
from tests import synthetic_pdfs as sp


class TestClassifier(unittest.TestCase):
    """One classification check per doc type — all 15 must route to the right enum."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _check(self, builder, expected: DocType):
        path = builder(self.tmp / f"{expected.value.lower()}.pdf")
        result = classify(path)
        self.assertEqual(result.doc_type, expected,
                         f"{expected.value}: anchor used = {result.matched_anchor!r}")
        self.assertEqual(result.confidence, "high")

    # Group A — Stage 2.
    def test_coi(self):              self._check(sp.write_coi, DocType.COI)
    def test_pan_card(self):         self._check(sp.write_pan_card, DocType.PAN_CARD)
    def test_tan_letter(self):       self._check(sp.write_tan_letter, DocType.TAN_LETTER)
    def test_aoa(self):              self._check(sp.write_aoa, DocType.AOA)
    def test_moa(self):              self._check(sp.write_moa, DocType.MOA)
    def test_gst_reg_06(self):       self._check(sp.write_gst_reg_06, DocType.GST_REG_06)
    def test_udyam(self):            self._check(sp.write_udyam, DocType.UDYAM)
    def test_mca_master_data(self):  self._check(sp.write_mca_master_data, DocType.MCA_MASTER_DATA)
    # Group B — classifier-only in Stage 2.
    def test_dir_12(self):           self._check(sp.write_dir_12, DocType.DIR_12)
    def test_mgt_14(self):           self._check(sp.write_mgt_14, DocType.MGT_14)
    def test_adt_1(self):            self._check(sp.write_adt_1, DocType.ADT_1)
    def test_adt_3(self):            self._check(sp.write_adt_3, DocType.ADT_3)
    def test_dir_3_kyc(self):        self._check(sp.write_dir_3_kyc, DocType.DIR_3_KYC)
    def test_srn_challan(self):      self._check(sp.write_srn_challan, DocType.SRN_CHALLAN)
    def test_dpt_3(self):            self._check(sp.write_dpt_3, DocType.DPT_3)


if __name__ == "__main__":
    unittest.main()
