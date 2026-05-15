"""
Smoke-test CLI for the parser.

Usage:
    python cli.py path/to/single.pdf
    python cli.py path/to/folder/                       # batch over every *.pdf
    python cli.py path/to/folder/ --persist             # also writes parser_* rows
    python cli.py path/to/folder/ --force <DOC_TYPE>    # skip classifier
    python cli.py path/to/folder/ --cin U72900MH...     # target_cin hint
    python cli.py --list-doc-types

Output is JSON-per-file on stdout (one JSON object per PDF, ``\\n`` separated).
Identifiers, controlled-vocab values and SRN are highlighted in the per-file
summary so off-vocab / format-invalid fields are easy to eyeball.

Exit code 0 if every file classified AND extracted; non-zero if any file failed
to classify or hit a Python exception. Persistence failures (HARD_FAIL etc.)
are surfaced in the JSON but don't change the exit code — they're an expected
part of a smoke-test.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Optional

from parser.classifier import DocType, classify
from parser.extractors import _DOC_MODULES, get_extractor


def _doc_types() -> list[str]:
    return [t.value for t in _DOC_MODULES]


def _summarise(extracted: dict) -> dict:
    """Pull a short "what landed" view that's easy to skim."""
    out: dict = {"doc_type": extracted.get("doc_type")}
    company = extracted.get("company") or {}
    out["company"] = {
        k: company.get(k) for k in ("cin", "pan", "tan", "legal_name", "date_of_incorporation")
        if company.get(k) is not None
    }
    if extracted.get("mca_filing"):
        out["mca_filing"] = {
            k: extracted["mca_filing"].get(k)
            for k in ("srn", "form_type", "purpose", "filing_date", "fee_paid")
            if extracted["mca_filing"].get(k) is not None
        }
    if extracted.get("registrations"):
        out["registrations"] = [
            {k: r.get(k) for k in ("type", "identifier") if r.get(k)}
            for r in extracted["registrations"]
        ]
    for list_key in ("directors_kmp", "moa_clauses", "aoa_clauses", "resolutions", "auditors", "deposits"):
        if extracted.get(list_key):
            out[f"{list_key}_count"] = len(extracted[list_key])
    if extracted.get("warnings"):
        out["warnings"] = extracted["warnings"]
    return out


def _run_one(path: Path, args: argparse.Namespace) -> dict:
    record: dict = {"file": str(path)}
    try:
        # Classify (unless --force).
        if args.force:
            doc_type = DocType(args.force)
            record["classified_as"] = doc_type.value
            record["forced"] = True
        else:
            result = classify(path)
            record["classified_as"] = result.doc_type.value if result.doc_type else None
            record["confidence"] = result.confidence
            record["matched_anchor"] = result.matched_anchor
            doc_type = result.doc_type

        if not doc_type:
            record["error"] = "classifier returned no doc type"
            return record

        extractor = get_extractor(doc_type)
        extracted = extractor(path)
        record["extracted"] = extracted if args.full else _summarise(extracted)

        if args.persist:
            from parser.persistence import persist
            r = persist(
                extracted,
                source_doc_type=doc_type.value,
                source_doc_id=str(path),
                target_cin=args.cin,
            )
            record["persist"] = {
                "accepted": r.accepted,
                "cin": r.cin,
                "rows_written": r.rows_written,
                "error": r.error,
                "issues": [
                    {"severity": i.severity.value, "rule": i.rule, "field": i.field, "message": i.message}
                    for i in r.issues
                ],
            }
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        if args.tracebacks:
            record["traceback"] = traceback.format_exc()
    return record


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Parser smoke-test CLI")
    ap.add_argument("path", nargs="?", help="PDF file or directory")
    ap.add_argument("--full", action="store_true", help="Emit the full extractor payload (default: summary)")
    ap.add_argument("--persist", action="store_true", help="Run persistence (requires DATABASE_URL)")
    ap.add_argument("--cin", help="target_cin hint for CIN-less docs (MoA / AoA)")
    ap.add_argument("--force", choices=_doc_types(), help="Skip classifier and force this doc type")
    ap.add_argument("--tracebacks", action="store_true", help="Include stack traces in errors")
    ap.add_argument("--list-doc-types", action="store_true")
    args = ap.parse_args(argv)

    if args.list_doc_types:
        for t in _doc_types():
            print(t)
        return 0

    if not args.path:
        ap.error("path is required (or use --list-doc-types)")

    root = Path(args.path)
    if root.is_file():
        files = [root]
    elif root.is_dir():
        files = sorted(root.glob("**/*.pdf"))
    else:
        print(json.dumps({"error": f"path not found: {root}"}), file=sys.stderr)
        return 2

    if not files:
        print(json.dumps({"warning": "no PDFs found"}), file=sys.stderr)
        return 0

    if args.persist and not os.environ.get("DATABASE_URL"):
        print(json.dumps({"error": "DATABASE_URL not set; --persist requires Postgres URL"}), file=sys.stderr)
        return 2

    any_failure = False
    for f in files:
        rec = _run_one(f, args)
        print(json.dumps(rec, default=str, ensure_ascii=False))
        if "error" in rec:
            any_failure = True
    return 1 if any_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
