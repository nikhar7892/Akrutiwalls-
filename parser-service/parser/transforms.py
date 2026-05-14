"""Value transforms used by playbook regex / acroform rules."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional


def to_iso_date(value: str) -> Optional[str]:
    """Parse common Indian date formats (DD-MM-YYYY, DD/MM/YYYY, etc.) → ISO."""
    if not value:
        return None
    value = value.strip()
    candidates = (
        "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
        "%Y-%m-%d", "%Y/%m/%d",
        "%d-%b-%Y", "%d %b %Y",
        "%d-%B-%Y", "%d %B %Y",
    )
    for fmt in candidates:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def to_number(value: str) -> Optional[float]:
    """Parse INR amounts: '₹ 1,23,456.78' / 'Rs. 50000' / '1,000' → float."""
    if value is None:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", str(value))
    if not cleaned or cleaned in ("-", ".", "-."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def to_int(value: str) -> Optional[int]:
    n = to_number(value)
    return int(n) if n is not None else None


def to_upper(value: str) -> Optional[str]:
    return value.upper().strip() if value else None


def to_fy(value: str) -> Optional[str]:
    """Normalize FY format → 'YYYY-YY' (e.g. '2023-24')."""
    if not value:
        return None
    v = value.strip().replace(" ", "")
    m = re.search(r"(\d{4})[-/](\d{2,4})", v)
    if m:
        start, end = m.group(1), m.group(2)
        if len(end) == 4:
            end = end[2:]
        return f"{start}-{end}"
    return v


TRANSFORMS = {
    "date": to_iso_date,
    "number": to_number,
    "int": to_int,
    "upper": to_upper,
    "fy": to_fy,
}


def apply_transform(name: Optional[str], value: Any) -> Any:
    if not name:
        return value if value is None or not isinstance(value, str) else value.strip()
    fn = TRANSFORMS.get(name)
    if fn is None:
        return value
    return fn(value)
