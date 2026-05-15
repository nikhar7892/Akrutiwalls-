"""
Articles of Association (eAoA INC-34 / printed AoA) — extractor.

Source of truth: project report §4 ('Articles of Association').
Per §4.D extraction:
  - Detect each Article by heading style (bold/centered single-line text matching
    Table F list) preceded by integer or roman numeral.
  - Build clause-tree storing (article_no, article_title, clause_no, clause_text).
  - Subscription block: anchor on 'Names, addresses, descriptions' or
    'In witness whereof'; iterate rows.
  - Store the full PDF + indexed headings + subscriber block; do NOT atomise sub-clauses.

Per Stage 2 brief: 'AoA — build a clause-tree keyed (cin, article_no,
article_title, clause_no) in a new parser_aoa_clauses table. Store raw clause
text. Promote only the flags the report calls out: "Seal optional?",
"Entrenched articles present?".'

Note: there is no destination column in the Stage 1 schema (or in the
two-table Stage 2 addition the user authorised) for the company-level AoA
flags. We surface them in the metadata block of the extract result so they
flow to the inconsistencies log / future display layer; persistence skips them.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

from pdfminer.high_level import extract_text


# Table F headings per report §4.B' (verbatim, ordered I..XXIII).
TABLE_F_HEADINGS: list[tuple[str, str]] = [
    ("I",     "Interpretation"),
    ("II",    "Share capital and variation of rights"),
    ("III",   "Lien"),
    ("IV",    "Calls on shares"),
    ("V",     "Transfer of shares"),
    ("VI",    "Transmission of shares"),
    ("VII",   "Forfeiture of shares"),
    ("VIII",  "Alteration of capital"),
    ("IX",    "Capitalisation of profits"),
    ("X",     "Buy-back of shares"),
    ("XI",    "General meetings"),
    ("XII",   "Proceedings at general meetings"),
    ("XIII",  "Adjournment of meeting"),
    ("XIV",   "Voting rights"),
    ("XV",    "Proxy"),
    ("XVI",   "Board of Directors"),
    ("XVII",  "Proceedings of the Board"),
    ("XVIII", "Chief Executive Officer, Manager, Company Secretary or CFO"),
    ("XIX",   "The Seal"),
    ("XX",    "Dividends and Reserve"),
    ("XXI",   "Accounts"),
    ("XXII",  "Winding up"),
    ("XXIII", "Indemnity"),
]


# Anchors per §4.C and §4.D.
_HEADER_RE = re.compile(r"ARTICLES\s+OF\s+ASSOCIATION\s+OF\s+(.+?)(?:\n|$)", re.IGNORECASE)
_SUBSCRIPTION_ANCHOR_PRIMARY = "Names, addresses, descriptions"
_SUBSCRIPTION_ANCHOR_FALLBACK = "In witness whereof"

# Flags per §4.E (kept verbatim labels from the report).
_FLAG_SEAL_OPTIONAL_RE = re.compile(
    r"\bSeal\b.*\b(?:optional|may|need\s+not)\b", re.IGNORECASE | re.DOTALL,
)
_FLAG_ENTRENCHED_RE = re.compile(
    r"\bentrenched\b|\bentrenchment\b", re.IGNORECASE,
)


def extract(pdf_path: Union[str, Path]) -> dict:
    text = extract_text(str(pdf_path)) or ""
    warnings: list[str] = []

    # Company name from the cover header per §4.C.
    legal_name = None
    m = _HEADER_RE.search(text)
    if m:
        legal_name = m.group(1).strip().rstrip(".,;:")

    # Build the clause tree by anchoring on each Table F heading; collect text
    # between this heading and the next (or to the subscription anchor).
    clauses: list[dict] = _build_clause_tree(text)

    # Subscription block per §4.D.
    subscription_text = _extract_subscription_block(text)

    # Per §4.E flags.
    flags = {
        "seal_optional": bool(_FLAG_SEAL_OPTIONAL_RE.search(text)),
        "entrenched_articles_present": bool(_FLAG_ENTRENCHED_RE.search(text)),
    }

    company_chunk = {"legal_name": legal_name}

    return {
        "doc_type": "AOA",
        "company": company_chunk,
        # Each clause row matches parser_aoa_clauses columns
        # (article_no, article_title, clause_no, clause_text).
        "aoa_clauses": clauses,
        "metadata": {
            "subscription_text": subscription_text,
            "flags": flags,
        },
        "warnings": warnings,
    }


def _build_clause_tree(text: str) -> list[dict]:
    """For each Table F heading present in the text, capture the body until the next heading."""
    if not text:
        return []
    upper_text = text  # heading match is case-insensitive

    # Find each heading's start position (first occurrence).
    heading_positions: list[tuple[int, str, str]] = []
    for art_no, title in TABLE_F_HEADINGS:
        # Anchor on the title (case-insensitive). Many AoAs use the same
        # phrasing as Table F itself.
        rx = re.compile(rf"\b{re.escape(title)}\b", re.IGNORECASE)
        m = rx.search(upper_text)
        if m:
            heading_positions.append((m.start(), art_no, title))

    if not heading_positions:
        return []

    # Sort by position, then take text-between as the clause body (the report says
    # do NOT atomise sub-clauses — we store the whole article body as one row
    # with clause_no = '0').
    heading_positions.sort(key=lambda x: x[0])
    clauses: list[dict] = []
    for i, (pos, art_no, title) in enumerate(heading_positions):
        end_pos = heading_positions[i + 1][0] if i + 1 < len(heading_positions) else len(text)
        body = text[pos:end_pos].strip()
        clauses.append({
            "article_no": art_no,
            "article_title": title,
            "clause_no": "0",
            "clause_text": body,
        })
    return clauses


def _extract_subscription_block(text: str) -> Optional[str]:
    """Return the subscription block per §4.D — anchor on the first matching phrase."""
    for anchor in (_SUBSCRIPTION_ANCHOR_PRIMARY, _SUBSCRIPTION_ANCHOR_FALLBACK):
        idx = text.lower().find(anchor.lower())
        if idx >= 0:
            return text[idx:].strip()
    return None
