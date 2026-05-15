"""
Cross-document validation skeleton tests. Encodes one positive and one
negative case per row of the report's validation matrix.
"""
import unittest

from parser.validation import (
    CrossDocInputs,
    Severity,
    has_hard_fail,
    reconcile_auditors_by_frn_or_membership,
    reconcile_directors_by_din,
    validate_capital_consistency,
    validate_cin_consistency,
    validate_company_record,
    validate_doi_against_cin_year,
    validate_legal_name_consistency,
    validate_pan_consistency,
    validate_registered_office_consistency,
)


CIN_OK = "U72900MH2018PTC123456"


class TestRule1CIN(unittest.TestCase):
    def test_no_issue_when_all_match(self):
        issues = validate_cin_consistency({
            "COI": CIN_OK, "MCA_MASTER_DATA": CIN_OK, "GST_REG_06": CIN_OK,
        })
        self.assertEqual(issues, [])

    def test_hard_fail_on_mismatch(self):
        issues = validate_cin_consistency({
            "COI": CIN_OK,
            "MCA_MASTER_DATA": "U72900MH2019PTC999999",
        })
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, Severity.HARD_FAIL)
        self.assertEqual(issues[0].field, "cin")


class TestRule2PAN(unittest.TestCase):
    def test_hard_fail_on_pan_mismatch(self):
        issues = validate_pan_consistency({
            "PAN_CARD": "AAACD1234E",
            "TAN_LETTER": "AAACD9999E",
        })
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, Severity.HARD_FAIL)


class TestRule3LegalName(unittest.TestCase):
    def test_soft_warn_with_case_tolerance(self):
        issues = validate_legal_name_consistency({
            "COI": "Demo Tech Private Limited",
            "MCA_MASTER_DATA": "DEMO TECH PRIVATE LIMITED",
        })
        self.assertEqual(issues, [])  # case tolerated

    def test_soft_warn_on_real_difference(self):
        issues = validate_legal_name_consistency({
            "COI": "Demo Tech Private Limited",
            "MCA_MASTER_DATA": "Demo Tech Pvt Ltd",
        })
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, Severity.SOFT_WARN)


class TestRule4DateOfIncorporation(unittest.TestCase):
    def test_hard_fail_when_year_mismatches_cin(self):
        issues = validate_doi_against_cin_year(CIN_OK, {
            "COI": "2017-06-15",   # CIN encodes 2018
        })
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, Severity.HARD_FAIL)

    def test_no_issue_when_year_matches(self):
        issues = validate_doi_against_cin_year(CIN_OK, {
            "COI": "2018-06-15",
            "MCA_MASTER_DATA": "2018-06-15",
        })
        self.assertEqual(issues, [])


class TestRule5RegisteredOffice(unittest.TestCase):
    def test_soft_warn_only(self):
        issues = validate_registered_office_consistency({
            "MCA_MASTER_DATA": "12 MG Road, Mumbai 400001",
            "GST_REG_06": "11 MG Road, Mumbai 400001",
        })
        self.assertTrue(issues)
        self.assertTrue(all(i.severity == Severity.SOFT_WARN for i in issues))


class TestRule6DirectorsReconcile(unittest.TestCase):
    def test_director_present_in_one_but_not_other(self):
        issues = reconcile_directors_by_din({
            "DIR_12":          ["00012345", "00098765"],
            "MCA_MASTER_DATA": ["00012345"],
        })
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, Severity.SOFT_WARN)
        self.assertIn("00098765", issues[0].message)


class TestRule7AuditorsReconcile(unittest.TestCase):
    def test_auditor_present_in_one_but_not_other(self):
        issues = reconcile_auditors_by_frn_or_membership({
            "ADT_1": ["012345N"],
            "AOC_4": ["012345N", "999999W"],
        })
        self.assertEqual(len(issues), 1)
        self.assertIn("999999W", issues[0].message)


class TestRule8Capital(unittest.TestCase):
    def test_soft_warn_on_capital_diff(self):
        issues = validate_capital_consistency({
            "MOA":             {"authorised": "Rs. 10,00,000", "paid_up": "1,00,000"},
            "MCA_MASTER_DATA": {"authorised": "1000000",        "paid_up": "100000"},
        })
        # Equal after stripping → no issue.
        self.assertEqual(issues, [])

    def test_diff_flagged(self):
        issues = validate_capital_consistency({
            "MOA":             {"authorised": "1000000", "paid_up": "100000"},
            "MCA_MASTER_DATA": {"authorised": "2000000", "paid_up": "100000"},
        })
        self.assertEqual(len(issues), 1)
        self.assertTrue(issues[0].field.endswith("authorised_capital"))


class TestOrchestrator(unittest.TestCase):
    def test_full_run_with_pan_derived_from_gstin(self):
        inputs = CrossDocInputs()
        inputs.cins = {"COI": CIN_OK, "MCA_MASTER_DATA": CIN_OK}
        inputs.pans = {"PAN_CARD": "AAPFU0939F", "TAN_LETTER": "AAPFU0939F"}
        inputs.add_pan_from_gstin("GST_REG_06", "27AAPFU0939F1ZV")
        inputs.legal_names = {
            "COI": "Demo Tech Private Limited",
            "MCA_MASTER_DATA": "DEMO TECH PRIVATE LIMITED",
        }
        inputs.dates_of_incorporation = {"COI": "2018-06-15"}
        inputs.director_lists = {"DIR_12": ["00012345"], "MCA_MASTER_DATA": ["00012345"]}
        issues = validate_company_record(inputs)
        self.assertFalse(has_hard_fail(issues))


if __name__ == "__main__":
    unittest.main()
