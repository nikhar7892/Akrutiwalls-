"""
Stage 2 end-to-end smoke test.

Builds synthetic PDFs for all 8 Group A documents using one consistent
fictional company, runs each through classifier → extractor → persistence,
then asserts the final state of the parser_* tables and the inconsistencies
log.
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


class TestStage2EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DATABASE_URL"):
            raise unittest.SkipTest("DATABASE_URL not set; E2E persistence test skipped")
        _truncate_parser_tables()

    def test_full_group_a_pipeline(self):
        tmp = Path(tempfile.mkdtemp())
        builders = [
            (sp.write_coi,             DocType.COI),
            (sp.write_pan_card,        DocType.PAN_CARD),
            (sp.write_tan_letter,      DocType.TAN_LETTER),
            (sp.write_aoa,             DocType.AOA),
            (sp.write_moa,             DocType.MOA),
            (sp.write_gst_reg_06,      DocType.GST_REG_06),
            (sp.write_udyam,           DocType.UDYAM),
            (sp.write_mca_master_data, DocType.MCA_MASTER_DATA),
        ]
        results = []
        for builder, expected_type in builders:
            path = builder(tmp / f"{expected_type.value.lower()}.pdf")

            # 1. Classifier returns correct doc type.
            cls = classify(path)
            self.assertEqual(cls.doc_type, expected_type, f"classifier missed on {expected_type}")

            # 2. Extractor returns a non-empty payload.
            extractor = get_extractor(expected_type)
            extracted = extractor(path)
            self.assertEqual(extracted["doc_type"], expected_type.value)

            # 3. Persistence writes successfully (no HARD_FAIL). MoA / AoA carry
            # no CIN of their own (the CIN is allotted at incorporation, AFTER
            # those docs are drafted) — the caller hints the workspace's CIN.
            target_hint = sp.SAMPLE_CIN if expected_type in (DocType.MOA, DocType.AOA) else None
            r = persist(
                extracted,
                source_doc_type=expected_type.value,
                source_doc_id=str(path),
                target_cin=target_hint,
            )
            self.assertTrue(r.accepted, f"{expected_type} persistence rejected: {r.error} / issues={r.issues}")
            results.append((expected_type, r))

        # 4. Final state of parser_company should be fully populated from the union.
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM parser_company WHERE cin = %s", (sp.SAMPLE_CIN,))
                company = cur.fetchone()
        self.assertIsNotNone(company)
        self.assertEqual(company["cin"], sp.SAMPLE_CIN)
        self.assertEqual(company["pan"], sp.SAMPLE_PAN)
        self.assertEqual(company["tan"], sp.SAMPLE_TAN)
        self.assertEqual(company["legal_name"], sp.SAMPLE_LEGAL_NAME)
        self.assertEqual(company["company_status"], "Active")
        self.assertEqual(company["listing_status"], "Unlisted")
        self.assertEqual(int(company["authorised_capital"]), sp.SAMPLE_AUTHORISED_CAPITAL)

        # 5. Child rows.
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM parser_moa_clauses WHERE cin = %s", (sp.SAMPLE_CIN,))
                self.assertGreaterEqual(cur.fetchone()["n"], 6)
                cur.execute("SELECT COUNT(*) AS n FROM parser_aoa_clauses WHERE cin = %s", (sp.SAMPLE_CIN,))
                self.assertGreaterEqual(cur.fetchone()["n"], 5)
                cur.execute("SELECT COUNT(*) AS n FROM parser_registrations WHERE cin = %s AND type = 'GST'", (sp.SAMPLE_CIN,))
                self.assertEqual(cur.fetchone()["n"], 1)
                cur.execute("SELECT COUNT(*) AS n FROM parser_registrations WHERE cin = %s AND type = 'UDYAM'", (sp.SAMPLE_CIN,))
                self.assertEqual(cur.fetchone()["n"], 1)
                cur.execute("SELECT COUNT(*) AS n FROM parser_directors_kmp WHERE cin = %s", (sp.SAMPLE_CIN,))
                self.assertEqual(cur.fetchone()["n"], 2)
                cur.execute("SELECT COUNT(*) AS n FROM parser_inconsistencies WHERE severity = 'hard_fail' AND cin = %s", (sp.SAMPLE_CIN,))
                self.assertEqual(cur.fetchone()["n"], 0, "no HARD_FAIL inconsistencies expected on consistent inputs")


if __name__ == "__main__":
    unittest.main()
