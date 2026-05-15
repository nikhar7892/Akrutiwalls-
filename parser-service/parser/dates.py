"""
Date helpers used by Group A extractors.

The COI uses the words form 'FIFTH day of APRIL two thousand twenty four';
GST REG-06 / Udyam / MCA Master Data use DD/MM/YYYY or DD-MM-YYYY. This
module isolates those parsers so each extractor stays small.

Source of truth for the words-to-date case: report §1.D
('Date is in words ... — implement a number-words-to-date parser').
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional


# Numeric / month-name parsers — the report mentions DD/MM/YYYY and DD-MM-YYYY
# patterns across §6 (GST REG-06), §7 (Udyam), §8 (MCA Master Data). Variations
# with month name (e.g. '15-Jun-2018') appear on COI / TAN letter prints.
_NUMERIC_PATTERNS = [
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%Y-%m-%d", "%Y/%m/%d",
    "%d-%b-%Y", "%d %b %Y",
    "%d-%B-%Y", "%d %B %Y",
    "%d %B, %Y",
]


def parse_numeric_date(text: str) -> Optional[date]:
    """Parse a single date string in any of the formats the report stipulates."""
    if not text:
        return None
    from datetime import datetime
    s = text.strip()
    for fmt in _NUMERIC_PATTERNS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# Words-to-date parser for the COI body.
# Report §1.C: "I hereby certify that <name> is incorporated on this <day> day of
# <month> two thousand <year>".
# Report §1.D: "Date is in words ('FIFTH day of APRIL two thousand twenty four')
# — implement a number-words-to-date parser."

_ORDINAL_WORDS: dict[str, int] = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
    "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20, "twenty-first": 21, "twenty-second": 22,
    "twenty-third": 23, "twenty-fourth": 24, "twenty-fifth": 25,
    "twenty-sixth": 26, "twenty-seventh": 27, "twenty-eighth": 28,
    "twenty-ninth": 29, "thirtieth": 30, "thirty-first": 31,
}

_MONTH_WORDS: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

# Numbers below 100 in word form; sufficient for "two thousand twenty four" style years.
_NUMBER_WORDS_TO_INT: dict[str, int] = {
    **{w: i for w, i in [
        ("zero", 0), ("one", 1), ("two", 2), ("three", 3), ("four", 4),
        ("five", 5), ("six", 6), ("seven", 7), ("eight", 8), ("nine", 9),
        ("ten", 10), ("eleven", 11), ("twelve", 12), ("thirteen", 13),
        ("fourteen", 14), ("fifteen", 15), ("sixteen", 16), ("seventeen", 17),
        ("eighteen", 18), ("nineteen", 19),
        ("twenty", 20), ("thirty", 30), ("forty", 40), ("fifty", 50),
        ("sixty", 60), ("seventy", 70), ("eighty", 80), ("ninety", 90),
    ]}
}


def _parse_words_under_100(text: str) -> Optional[int]:
    """Parse 'twenty four', 'twenty-four', 'fifteen' → 24/24/15. None if unparseable."""
    s = text.strip().lower().replace("-", " ")
    parts = [p for p in s.split() if p]
    if len(parts) == 1 and parts[0] in _NUMBER_WORDS_TO_INT:
        return _NUMBER_WORDS_TO_INT[parts[0]]
    if len(parts) == 2 and parts[0] in _NUMBER_WORDS_TO_INT and parts[1] in _NUMBER_WORDS_TO_INT:
        a, b = _NUMBER_WORDS_TO_INT[parts[0]], _NUMBER_WORDS_TO_INT[parts[1]]
        if a in (20, 30, 40, 50, 60, 70, 80, 90) and b < 10:
            return a + b
    return None


# Pattern matches "FIFTH day of APRIL two thousand " — we match the prefix,
# then the year-tail is parsed separately by trying 1 and 2 trailing word(s)
# against the words-to-int table (longest valid match wins).
_COI_WORDS_DATE_PREFIX_RE = re.compile(
    r"\b([A-Za-z][A-Za-z\-]+)\s+day\s+of\s+([A-Za-z]+)\s+two\s+thousand\s+",
    re.IGNORECASE,
)
# After the prefix we expect 1–2 lowercase-or-hyphen-only year words.
_YEAR_TAIL_TOKENS_RE = re.compile(r"\b([A-Za-z\-]+)\b")


def parse_coi_words_date(text: str) -> Optional[date]:
    """Parse a single instance of the COI-style words date out of the surrounding text."""
    if not text:
        return None
    m = _COI_WORDS_DATE_PREFIX_RE.search(text)
    if not m:
        return None
    day_word = m.group(1).lower().replace(" ", "-")
    month_word = m.group(2).lower()
    day = _ORDINAL_WORDS.get(day_word)
    month = _MONTH_WORDS.get(month_word)
    if not (day and month):
        return None

    # Take the next ~30 characters after the prefix and pull up to two word
    # tokens. Try a 2-token year first (e.g., "twenty four"), fall back to 1.
    tail = text[m.end() : m.end() + 30]
    tokens = _YEAR_TAIL_TOKENS_RE.findall(tail)
    if not tokens:
        return None
    year_tail: Optional[int] = None
    if len(tokens) >= 2:
        year_tail = _parse_words_under_100(f"{tokens[0]} {tokens[1]}")
    if year_tail is None:
        year_tail = _parse_words_under_100(tokens[0])
    if year_tail is None:
        return None
    try:
        return date(2000 + year_tail, month, day)
    except ValueError:
        return None
