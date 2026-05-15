"""DIR-3 KYC tests, including the S3-R2 triennial due-date logic (both branches)."""
import tempfile
import unittest
from datetime import date
from pathlib import Path

from parser.extractors.dir_3_kyc import (
    KYC_TRANSITIONAL_DUE,
    KYC_TRIENNIAL_EFFECTIVE,
    compute_kyc_due_date,
    extract,
)
from tests import synthetic_pdfs as sp


class TestKycDueDateLogic(unittest.TestCase):
    """S3-R2 branches as stated in the report §13 and PIB PRID=2210552."""

    def test_filed_before_31_mar_2026_due_2028_06_30(self):
        # Per PIB PRID=2210552 quoted in §13.A: directors who filed before
        # 31 March 2026 have next KYC due 30 June 2028.
        self.assertEqual(compute_kyc_due_date(date(2024, 6, 30)), KYC_TRANSITIONAL_DUE)
        self.assertEqual(compute_kyc_due_date(date(2025, 12, 31)), KYC_TRANSITIONAL_DUE)
        # Boundary: 2026-03-30 is still < effective date → transitional rule.
        self.assertEqual(compute_kyc_due_date(date(2026, 3, 30)), KYC_TRANSITIONAL_DUE)

    def test_filed_on_or_after_31_mar_2026_plus_3_years(self):
        # Triennial cycle from the filing date.
        self.assertEqual(
            compute_kyc_due_date(KYC_TRIENNIAL_EFFECTIVE),
            date(2029, 3, 31),
        )
        self.assertEqual(
            compute_kyc_due_date(date(2027, 6, 30)),
            date(2030, 6, 30),
        )
        # Leap-day filing → triennial fallback to Feb 28.
        self.assertEqual(
            compute_kyc_due_date(date(2028, 2, 29)),
            date(2031, 2, 28),
        )

    def test_none_in_none_out(self):
        self.assertIsNone(compute_kyc_due_date(None))


class TestDir3KycExtractor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_happy_path_pre_31mar2026_filing(self):
        pdf = sp.write_dir_3_kyc(self.tmp / "kyc.pdf", filed_on="30/06/2024")
        out = extract(pdf)
        self.assertEqual(out["doc_type"], "DIR_3_KYC")
        self.assertEqual(out["mca_filing"]["srn"], sp.SAMPLE_SRN_DIR_3_KYC)
        directors = out["directors_kmp"]
        self.assertEqual(len(directors), 1)
        d = directors[0]
        self.assertEqual(d["din"], sp.SAMPLE_DIN_1)
        self.assertEqual(d["din_or_pan"], sp.SAMPLE_DIN_1)
        self.assertEqual(d["aadhaar_last4"], "1234")
        self.assertEqual(d["kyc_last_filed_date"], "2024-06-30")
        # S3-R2 branch (a): filed before 31 March 2026 → due 30 June 2028.
        self.assertEqual(d["kyc_due_date"], "2028-06-30")

    def test_post_31mar2026_filing_triennial_branch(self):
        pdf = sp.write_dir_3_kyc(self.tmp / "kyc_post.pdf", filed_on="15/04/2026")
        out = extract(pdf)
        d = out["directors_kmp"][0]
        # +3 years exact-date.
        self.assertEqual(d["kyc_last_filed_date"], "2026-04-15")
        self.assertEqual(d["kyc_due_date"], "2029-04-15")


if __name__ == "__main__":
    unittest.main()
