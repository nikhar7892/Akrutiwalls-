"""
Stage 3 end-to-end smoke test.

Runs all 7 Group B documents for the same fictional company that Stage 2
uses, asserts the final state of the MCA-filings + child tables, AND
verifies that the Stage 2 E2E remains green (re-asserts a few row counts
unchanged after Stage 3 docs land).

Does NOT modify the Stage 2 test file.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from parser.classifier import DocType, classify
from parser.extractors import get_extractor
from parser.persistence import persist
from tests import synthetic_pdfs as sp


def _conn():
    return psycopg.connect(os.environ["DATABASE_URL"].split("?")[0], row_factory=dict_row)


def _truncate_parser_tables() -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                TRUNCATE
                  parser_inconsistencies,
                  parser_aoa_clauses,
                  parser_moa_clauses,
                  parser_directors_kmp,
                  parser_registrations,
                  parser_resolutions_agreements,
                  parser_deposits,
                  parser_auditors,
                  parser_mca_filings,
                  parser_company
                CASCADE
            """)
        conn.commit()


GROUP_A_BUILDERS = [
    (sp.write_coi,             DocType.COI),
    (sp.write_pan_card,        DocType.PAN_CARD),
    (sp.write_tan_letter,      DocType.TAN_LETTER),
    (sp.write_aoa,             DocType.AOA),
    (sp.write_moa,             DocType.MOA),
    (sp.write_gst_reg_06,      DocType.GST_REG_06),
    (sp.write_udyam,           DocType.UDYAM),
    (sp.write_mca_master_data, DocType.MCA_MASTER_DATA),
]

GROUP_B_BUILDERS = [
    (sp.write_dir_12,      DocType.DIR_12,      sp.SAMPLE_SRN_DIR_12),
    (sp.write_mgt_14,      DocType.MGT_14,      sp.SAMPLE_SRN_MGT_14),
    (sp.write_adt_1,       DocType.ADT_1,       sp.SAMPLE_SRN_ADT_1),
    (sp.write_adt_3,       DocType.ADT_3,       sp.SAMPLE_SRN_ADT_3),
    (sp.write_dir_3_kyc,   DocType.DIR_3_KYC,   sp.SAMPLE_SRN_DIR_3_KYC),
    (sp.write_srn_challan, DocType.SRN_CHALLAN, sp.SAMPLE_SRN_CHALLAN),
    (sp.write_dpt_3,       DocType.DPT_3,       sp.SAMPLE_SRN_DPT_3),
]


class TestStage3EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DATABASE_URL"):
            raise unittest.SkipTest("DATABASE_URL not set; Stage 3 E2E skipped")
        _truncate_parser_tables()
        # Land Group A first so the parser_company row exists for Group B docs
        # whose 'mca_filing' rows need an existing CIN FK target.
        tmp = Path(tempfile.mkdtemp(prefix="stage3_grpa_"))
        for builder, expected_type in GROUP_A_BUILDERS:
            path = builder(tmp / f"{expected_type.value.lower()}.pdf")
            cls_result = classify(path)
            assert cls_result.doc_type == expected_type
            extracted = get_extractor(expected_type)(path)
            target_hint = sp.SAMPLE_CIN if expected_type in (DocType.MOA, DocType.AOA) else None
            r = persist(extracted, source_doc_type=expected_type.value,
                        source_doc_id=str(path), target_cin=target_hint)
            assert r.accepted, f"{expected_type} setup failed: {r.error} / {r.issues}"
        cls.tmp = Path(tempfile.mkdtemp(prefix="stage3_grpb_"))

    def test_full_group_b_pipeline(self):
        results = {}
        for builder, expected_type, expected_srn in GROUP_B_BUILDERS:
            path = builder(self.tmp / f"{expected_type.value.lower()}.pdf")
            # 1. Classifier returns correct doc type (Stage 2 wiring re-asserted).
            cls = classify(path)
            self.assertEqual(cls.doc_type, expected_type, f"classifier missed on {expected_type}")

            # 2. Extractor returns a non-empty mca_filing chunk with the right SRN.
            extracted = get_extractor(expected_type)(path)
            self.assertEqual(extracted["doc_type"], expected_type.value)
            self.assertEqual(extracted["mca_filing"]["srn"], expected_srn)

            # 3. Persistence — SRN-first. Should accept all 7 cleanly.
            r = persist(extracted, source_doc_type=expected_type.value,
                        source_doc_id=str(path))
            self.assertTrue(r.accepted, f"{expected_type} persistence rejected: {r.error} / {r.issues}")
            self.assertEqual(r.cin, sp.SAMPLE_CIN)
            results[expected_type] = r

        # ------------------------------------------------------------------
        # Final state assertions.
        # ------------------------------------------------------------------
        with _conn() as conn:
            with conn.cursor() as cur:
                # 7 new parser_mca_filings rows present, all SRNs distinct.
                cur.execute(
                    "SELECT srn FROM parser_mca_filings WHERE cin = %s ORDER BY srn",
                    (sp.SAMPLE_CIN,),
                )
                srns = [r["srn"] for r in cur.fetchall()]
                expected_srns = sorted(s for _, _, s in GROUP_B_BUILDERS)
                self.assertEqual(sorted(srns), expected_srns)
                self.assertEqual(len(set(srns)), 7, "All SRNs must be distinct")

                # DIR-12 directors landed.
                cur.execute(
                    "SELECT din FROM parser_directors_kmp WHERE cin = %s ORDER BY din",
                    (sp.SAMPLE_CIN,),
                )
                dins = [r["din"] for r in cur.fetchall()]
                self.assertIn(sp.SAMPLE_DIN_1, dins)
                self.assertIn(sp.SAMPLE_DIN_2, dins)

                # MGT-14 resolutions landed (≥ 2 — repeating section iteration verified).
                cur.execute(
                    "SELECT COUNT(*) AS n FROM parser_resolutions_agreements "
                    "WHERE cin = %s AND mgt14_srn = %s",
                    (sp.SAMPLE_CIN, sp.SAMPLE_SRN_MGT_14),
                )
                self.assertGreaterEqual(cur.fetchone()["n"], 2)

                # ADT-1 auditor landed with adt1_srn populated.
                cur.execute(
                    "SELECT * FROM parser_auditors WHERE cin = %s AND frn_or_membership_no = %s",
                    (sp.SAMPLE_CIN, sp.SAMPLE_FRN),
                )
                auditor = cur.fetchone()
                self.assertIsNotNone(auditor)
                self.assertEqual(auditor["adt1_srn"], sp.SAMPLE_SRN_ADT_1)
                # ADT-3 updated the SAME row.
                self.assertEqual(auditor["adt3_srn"], sp.SAMPLE_SRN_ADT_3)
                self.assertIsNotNone(auditor["resignation_date"])

                # DIR-3 KYC updated the director landed by DIR-12.
                cur.execute(
                    "SELECT kyc_last_filed_date, kyc_due_date FROM parser_directors_kmp "
                    "WHERE cin = %s AND din = %s",
                    (sp.SAMPLE_CIN, sp.SAMPLE_DIN_1),
                )
                kyc_row = cur.fetchone()
                self.assertIsNotNone(kyc_row["kyc_last_filed_date"])
                # S3-R2: filing 30/06/2024 → next due 30/06/2028.
                self.assertEqual(str(kyc_row["kyc_due_date"]), "2028-06-30")

                # DPT-3 deposits row with dpt3_srn populated.
                cur.execute(
                    "SELECT * FROM parser_deposits WHERE cin = %s",
                    (sp.SAMPLE_CIN,),
                )
                dep = cur.fetchone()
                self.assertIsNotNone(dep)
                self.assertEqual(dep["dpt3_srn"], sp.SAMPLE_SRN_DPT_3)
                self.assertEqual(dep["financial_year"], "2023-24")

                # No HARD_FAIL inconsistencies on this consistent input set.
                cur.execute(
                    "SELECT COUNT(*) AS n FROM parser_inconsistencies "
                    "WHERE severity = 'hard_fail' AND cin = %s",
                    (sp.SAMPLE_CIN,),
                )
                self.assertEqual(cur.fetchone()["n"], 0,
                                 "no HARD_FAIL inconsistencies expected on consistent inputs")

                # Stage 2 child tables remain populated (Group A landed in setUpClass).
                cur.execute("SELECT COUNT(*) AS n FROM parser_moa_clauses WHERE cin = %s",
                            (sp.SAMPLE_CIN,))
                self.assertGreaterEqual(cur.fetchone()["n"], 6)
                cur.execute("SELECT COUNT(*) AS n FROM parser_registrations WHERE cin = %s",
                            (sp.SAMPLE_CIN,))
                self.assertGreaterEqual(cur.fetchone()["n"], 2)

    def test_srn_missing_returns_hard_fail(self):
        # Build a DIR-12-like extract with NO srn — persistence must HARD_FAIL
        # per S3-R1 and NOT write any rows.
        bogus = {
            "doc_type": "DIR_12",
            "company": {"cin": sp.SAMPLE_CIN},
            "mca_filing": {"form_type": "DIR-12"},  # no srn
            "directors_kmp": [{"din": sp.SAMPLE_DIN_1, "din_or_pan": sp.SAMPLE_DIN_1, "name": "X"}],
            "warnings": [],
        }
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM parser_mca_filings WHERE cin = %s",
                            (sp.SAMPLE_CIN,))
                before = cur.fetchone()["n"]

        r = persist(bogus, source_doc_type="DIR_12", source_doc_id="bogus.pdf")
        self.assertFalse(r.accepted)
        self.assertIn("SRN", (r.error or ""))
        self.assertEqual(len(r.issues), 1)
        self.assertEqual(r.issues[0].rule, "srn_required_for_mca_filing")

        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM parser_mca_filings WHERE cin = %s",
                            (sp.SAMPLE_CIN,))
                after = cur.fetchone()["n"]
        self.assertEqual(before, after, "HARD_FAIL must NOT write any row")


if __name__ == "__main__":
    unittest.main()
