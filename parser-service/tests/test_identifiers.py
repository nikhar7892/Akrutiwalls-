"""
Identifier-library tests. Format strings are derived verbatim from the
project report; do not invent samples that don't conform to the report's
regex statements.
"""
import unittest

from parser import identifiers as ids
from parser.identifiers import PAN_ENTITY_TYPE
from parser.validation import derive_pan_from_gstin


# Sample identifier values used across the suite.
SAMPLE_CIN_UNLISTED = "U72900MH2018PTC123456"
SAMPLE_CIN_LISTED = "L72900MH2018PLC123456"
SAMPLE_PAN_COMPANY = "AAACD1234E"      # 4th char 'C' = Company
SAMPLE_TAN = "BLRA12345B"
SAMPLE_DIN = "00012345"
SAMPLE_SRN = "T12345678"
SAMPLE_UDYAM = "UDYAM-MH-19-0054448"   # from the report's Udyam section
SAMPLE_IEC = "AAACD1234E"              # = entity's PAN per report
# Authentic sample GSTIN (publicly listed test vector, valid Luhn-mod-36).
SAMPLE_GSTIN = "27AAPFU0939F1ZV"


class TestIdentifierRegexes(unittest.TestCase):
    def test_cin_format(self):
        self.assertTrue(ids.is_valid_cin(SAMPLE_CIN_UNLISTED))
        self.assertTrue(ids.is_valid_cin(SAMPLE_CIN_LISTED))
        self.assertFalse(ids.is_valid_cin("X72900MH2018PTC123456"))   # 1st char must be L or U
        self.assertFalse(ids.is_valid_cin("U72900MH2018PTC12345"))    # too short
        self.assertFalse(ids.is_valid_cin(""))

    def test_pan_format_and_entity_type(self):
        self.assertTrue(ids.is_valid_pan(SAMPLE_PAN_COMPANY))
        # 4th-char map verbatim from report
        self.assertEqual(PAN_ENTITY_TYPE["C"], "Company")
        self.assertEqual(PAN_ENTITY_TYPE["P"], "Individual")
        self.assertEqual(PAN_ENTITY_TYPE["G"], "Government")
        # parse_pan exposes the entity-type label
        parts = ids.parse_pan(SAMPLE_PAN_COMPANY)
        self.assertEqual(parts.entity_type_code, "C")
        self.assertEqual(parts.entity_type_label, "Company")

    def test_tan_format(self):
        self.assertTrue(ids.is_valid_tan(SAMPLE_TAN))
        parts = ids.parse_tan(SAMPLE_TAN)
        self.assertEqual(parts.city_or_rcc_code, "BLR")
        self.assertEqual(parts.deductor_initial, "A")

    def test_din_format(self):
        self.assertTrue(ids.is_valid_din(SAMPLE_DIN))
        self.assertFalse(ids.is_valid_din("0001234"))   # 7 digits
        self.assertFalse(ids.is_valid_din("00012345A"))  # alpha not allowed

    def test_srn_format(self):
        self.assertTrue(ids.is_valid_srn(SAMPLE_SRN))
        self.assertFalse(ids.is_valid_srn("12345678"))    # must start with letter
        self.assertFalse(ids.is_valid_srn("Z9999999"))    # 8 chars, too short
        # Per report, V3 also rejects placeholder Z99999999 — but that's a server-side rule;
        # here we only enforce format.
        self.assertTrue(ids.is_valid_srn("Z99999999"))

    def test_udyam_format(self):
        self.assertTrue(ids.is_valid_udyam(SAMPLE_UDYAM))
        parts = ids.parse_udyam(SAMPLE_UDYAM)
        self.assertEqual(parts.state_code, "MH")
        self.assertEqual(parts.district_code, "19")
        self.assertEqual(parts.serial, "0054448")

    def test_iec_equals_pan_when_expected(self):
        self.assertTrue(ids.is_valid_iec(SAMPLE_IEC))
        self.assertTrue(ids.is_valid_iec(SAMPLE_IEC, expected_pan=SAMPLE_PAN_COMPANY))
        self.assertFalse(ids.is_valid_iec(SAMPLE_IEC, expected_pan="ZZZZZ9999Z"))

    def test_llpin_format_TODO_sample(self):
        # TODO: confirm with sample (report items §3). Both shapes accepted today.
        self.assertTrue(ids.is_valid_llpin("ABC1234"))
        self.assertTrue(ids.is_valid_llpin("ABC-1234"))

    def test_fcrn_format_TODO_sample(self):
        # TODO: confirm with sample (report items §2).
        self.assertTrue(ids.is_valid_fcrn("F12345"))
        self.assertFalse(ids.is_valid_fcrn("X12345"))


class TestGstinChecksum(unittest.TestCase):
    def test_check_char_for_known_sample(self):
        # Compute the check char for the first 14 chars and confirm it equals position 15.
        body = SAMPLE_GSTIN[:14]
        self.assertEqual(ids.gstin_check_char(body), SAMPLE_GSTIN[14])

    def test_full_validator(self):
        self.assertTrue(ids.is_valid_gstin(SAMPLE_GSTIN))
        # Flip the check digit → should fail.
        broken = SAMPLE_GSTIN[:14] + ("0" if SAMPLE_GSTIN[14] != "0" else "1")
        self.assertFalse(ids.is_valid_gstin(broken))

    def test_format_only_failures(self):
        # Wrong state-code length, position 14 not 'Z', position 13 not [1-9A-Z], etc.
        self.assertFalse(ids.is_valid_gstin("9AAACD1234E1ZV"))   # 14 chars, too short
        self.assertFalse(ids.is_valid_gstin("27AAACD1234E0ZV"))  # position 13 = '0' (regex disallows)


class TestStructuralParsers(unittest.TestCase):
    def test_parse_cin(self):
        parts = ids.parse_cin(SAMPLE_CIN_UNLISTED)
        self.assertEqual(parts.listing_status, "U")
        self.assertEqual(parts.nic_code, "72900")
        self.assertEqual(parts.state_code, "MH")
        self.assertEqual(parts.year, 2018)
        self.assertEqual(parts.company_type, "PTC")
        self.assertEqual(parts.roc_serial, "123456")

    def test_parse_gstin_breakdown(self):
        parts = ids.parse_gstin(SAMPLE_GSTIN)
        self.assertEqual(parts.state_code, "27")
        self.assertEqual(parts.pan, SAMPLE_GSTIN[2:12])
        self.assertEqual(parts.entity_code, SAMPLE_GSTIN[12])
        self.assertEqual(parts.z, "Z")
        self.assertEqual(parts.check, SAMPLE_GSTIN[14])

    def test_derive_pan_from_gstin(self):
        # Pulled into validation.py per report 'GSTIN[3:13] == PAN' rule.
        self.assertEqual(derive_pan_from_gstin(SAMPLE_GSTIN), SAMPLE_GSTIN[2:12])


if __name__ == "__main__":
    unittest.main()
