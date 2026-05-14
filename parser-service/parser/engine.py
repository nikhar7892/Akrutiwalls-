"""
Playbook engine.

A playbook = one YAML file per MCA form. The engine:
  1. Loads every YAML in `playbooks/` at startup.
  2. Picks the matching playbook for an uploaded PDF (text_contains / hint).
  3. Runs the playbook's AcroForm map + regex map + defaults.
  4. Returns a `{path: {value, source, confidence}}` extract.

Each extract slot carries its source (acroform | regex | default | llm | ocr) so
the review UI can show field-by-field provenance. The user accepts → fields flow
into the existing Next.js server actions that already power manual entry.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from parser.pdf import PdfBundle
from parser.transforms import apply_transform

log = logging.getLogger(__name__)


@dataclass
class Playbook:
    form: str
    path: str
    description: str = ""
    match: dict = field(default_factory=dict)
    acroform: dict[str, str] = field(default_factory=dict)
    regex: list[dict] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    defaults: dict[str, Any] = field(default_factory=dict)
    writes_to: list[dict] = field(default_factory=list)
    llm_hints: dict[str, Any] = field(default_factory=dict)


class PlaybookEngine:
    def __init__(self, playbook_dir: str = "playbooks") -> None:
        self.playbook_dir = playbook_dir
        self.playbooks: list[Playbook] = []
        self._load_all()

    # ---------- public API ----------

    def list_playbooks(self) -> list[str]:
        return [p.form for p in self.playbooks]

    def describe_playbooks(self) -> list[dict]:
        return [
            {
                "form": p.form,
                "description": p.description,
                "writes_to": [w.get("entity") for w in p.writes_to],
            }
            for p in self.playbooks
        ]

    def match(self, bundle: PdfBundle, hint_form: Optional[str] = None) -> Optional[Playbook]:
        if hint_form:
            for p in self.playbooks:
                if p.form.upper() == hint_form.upper():
                    return p
        scored: list[tuple[int, Playbook]] = []
        for p in self.playbooks:
            score = self._match_score(p, bundle)
            if score > 0:
                scored.append((score, p))
        if not scored:
            return None
        scored.sort(reverse=True, key=lambda x: x[0])
        return scored[0][1]

    def run(self, p: Playbook, bundle: PdfBundle) -> dict:
        extract: dict[str, dict[str, dict]] = {}

        # 1. AcroForm fields (highest confidence — the form itself told us)
        for acroform_name, target_path in p.acroform.items():
            raw = self._find_acroform(bundle.acroform, acroform_name)
            if raw not in (None, ""):
                self._set(extract, target_path, raw, source="acroform", confidence=0.98)

        # 2. Regex extractors against the page text
        for rule in p.regex:
            pattern = rule.get("pattern")
            target = rule.get("field")
            if not pattern or not target:
                continue
            try:
                m = re.search(pattern, bundle.text, flags=re.IGNORECASE | re.MULTILINE)
            except re.error as exc:
                log.warning("bad regex in %s for %s: %s", p.form, target, exc)
                continue
            if not m:
                continue
            grp = rule.get("group", 1)
            try:
                value = m.group(grp)
            except IndexError:
                continue
            value = apply_transform(rule.get("transform"), value)
            if value in (None, ""):
                continue
            # Don't overwrite an AcroForm hit — it's higher signal.
            if self._has(extract, target):
                continue
            self._set(extract, target, value, source="regex", confidence=rule.get("confidence", 0.9))

        # 3. Tables — extract repeating rows (e.g. MOA subscribers) into list entities
        for table_rule in p.tables:
            rows = self._extract_table_rows(bundle.tables, table_rule)
            if rows:
                target = str(table_rule.get("target", "rows"))
                extract[target] = rows  # list of {field: slot} records

        # 4. Defaults — fill anything still empty
        for target, value in p.defaults.items():
            if self._has(extract, target):
                continue
            self._set(extract, target, value, source="default", confidence=0.7)

        # 4. Final transform pass for AcroForm values (regex already transformed inline)
        for entity, fields_ in extract.items():
            if not isinstance(fields_, dict):
                continue  # list entities (subscribers, directors) skip this pass
            for field_name, slot in fields_.items():
                if not isinstance(slot, dict):
                    continue
                if slot.get("source") == "acroform":
                    transform_name = self._writes_to_transform(p, entity, field_name)
                    if transform_name:
                        slot["value"] = apply_transform(transform_name, slot["value"])

        extract["_meta"] = {
            "playbook": p.form,
            "ocr_used": bundle.ocr_used,
            "acroform_fields_seen": len(bundle.acroform),
            "page_count": bundle.page_count,
        }
        return extract

    def confidence_label(self, extract: dict) -> str:
        scores: list[float] = []
        for k, v in extract.items():
            if k.startswith("_"):
                continue
            if isinstance(v, dict):
                for slot in v.values():
                    if isinstance(slot, dict) and "confidence" in slot:
                        scores.append(float(slot["confidence"]))
            elif isinstance(v, list):
                for row in v:
                    if not isinstance(row, dict):
                        continue
                    for slot in row.values():
                        if isinstance(slot, dict) and "confidence" in slot:
                            scores.append(float(slot["confidence"]))
        if not scores:
            return "none"
        avg = sum(scores) / len(scores)
        if avg >= 0.9:
            return "high"
        if avg >= 0.75:
            return "medium"
        return "low"

    # ---------- internals ----------

    def _load_all(self) -> None:
        base = Path(self.playbook_dir)
        if not base.exists():
            log.warning("playbook dir not found: %s", base)
            return
        for path in sorted(base.glob("*.yaml")):
            if path.name.startswith("_"):
                continue
            try:
                with open(path) as fh:
                    data = yaml.safe_load(fh) or {}
                pb = Playbook(
                    form=str(data["form"]).upper(),
                    path=str(path),
                    description=data.get("description", ""),
                    match=data.get("match", {}),
                    acroform={str(k): str(v) for k, v in (data.get("acroform") or {}).items()},
                    regex=list(data.get("regex") or []),
                    tables=list(data.get("tables") or []),
                    defaults=dict(data.get("defaults") or {}),
                    writes_to=list(data.get("writes_to") or []),
                    llm_hints=dict(data.get("llm") or {}),
                )
                self.playbooks.append(pb)
                log.info("loaded playbook %s from %s", pb.form, path)
            except Exception as exc:  # noqa: BLE001
                log.error("failed to load playbook %s: %s", path, exc)

    def _match_score(self, p: Playbook, bundle: PdfBundle) -> int:
        match = p.match or {}
        text = bundle.text.lower()
        score = 0
        for needle in match.get("text_contains", []) or []:
            if needle.lower() in text:
                score += 5
        for needle in match.get("text_contains_any", []) or []:
            if needle.lower() in text:
                score += 3
                break
        for acroform_name in match.get("acroform_has", []) or []:
            if acroform_name in bundle.acroform:
                score += 4
        # bare filename hint
        fname = bundle.filename.lower()
        if p.form.lower().replace("-", "") in fname.replace("-", "").replace("_", ""):
            score += 2
        return score

    def _find_acroform(self, fields: dict[str, str], wanted: str) -> Optional[str]:
        if wanted in fields:
            return fields[wanted]
        wl = wanted.lower()
        for k, v in fields.items():
            if k.lower() == wl:
                return v
        for k, v in fields.items():
            if wl in k.lower():
                return v
        return None

    def _set(self, extract: dict, path: str, value: Any, source: str, confidence: float) -> None:
        if "." not in path:
            entity, field_name = "_root", path
        else:
            entity, field_name = path.split(".", 1)
        extract.setdefault(entity, {})[field_name] = {
            "value": value,
            "source": source,
            "confidence": confidence,
        }

    def _has(self, extract: dict, path: str) -> bool:
        if "." not in path:
            entity, field_name = "_root", path
        else:
            entity, field_name = path.split(".", 1)
        return field_name in extract.get(entity, {})

    def _writes_to_transform(self, p: Playbook, entity: str, field_name: str) -> Optional[str]:
        for w in p.writes_to:
            if w.get("entity", "").lower() == entity.lower():
                transforms = w.get("transforms") or {}
                return transforms.get(field_name)
        return None

    # ---------- table extraction ----------

    def _extract_table_rows(
        self,
        tables: list[list[list[Optional[str]]]],
        rule: dict,
    ) -> list[dict[str, dict]]:
        """Find the first table that matches `rule`, map columns by header, return rows."""
        columns_spec = rule.get("columns") or []
        if not columns_spec:
            return []
        min_data_rows = int(rule.get("min_data_rows", 1))
        require = list(rule.get("require") or [])

        for table in tables:
            if not table or len(table) < 1 + min_data_rows:
                continue
            mapping = self._match_table_header(table, columns_spec)
            if not mapping:
                continue
            # `mapping` is {field_name: column_index}. Skip the header row and iterate data rows.
            rows: list[dict[str, dict]] = []
            header_row_idx = self._find_header_row(table, columns_spec)
            for raw_row in table[header_row_idx + 1 :]:
                if not raw_row:
                    continue
                record: dict[str, dict] = {}
                for field_name, col_idx in mapping.items():
                    if col_idx >= len(raw_row):
                        continue
                    cell = raw_row[col_idx]
                    if cell is None:
                        continue
                    value = str(cell).strip()
                    if not value:
                        continue
                    spec = next((c for c in columns_spec if c.get("field") == field_name), {})
                    transformed = apply_transform(spec.get("transform"), value)
                    if transformed in (None, ""):
                        continue
                    record[field_name] = {
                        "value": transformed,
                        "source": "table",
                        "confidence": float(spec.get("confidence", 0.85)),
                    }
                # Drop rows that don't satisfy required fields.
                if require and not all(record.get(r) for r in require):
                    continue
                if record:
                    rows.append(record)
            if len(rows) >= min_data_rows:
                return rows
        return []

    def _find_header_row(
        self,
        table: list[list[Optional[str]]],
        columns_spec: list[dict],
    ) -> int:
        """Header is the first row where any cell matches any column's `matches` regex."""
        for idx, row in enumerate(table):
            if self._row_matches_header(row, columns_spec):
                return idx
        return 0

    def _row_matches_header(
        self,
        row: list[Optional[str]],
        columns_spec: list[dict],
    ) -> bool:
        joined = " ".join((c or "").lower() for c in row)
        if not joined.strip():
            return False
        for spec in columns_spec:
            pattern = spec.get("matches")
            if pattern and re.search(pattern, joined, flags=re.IGNORECASE):
                return True
        return False

    def _match_table_header(
        self,
        table: list[list[Optional[str]]],
        columns_spec: list[dict],
    ) -> dict[str, int]:
        """Return {field_name: column_index} for columns identifiable in the header row."""
        header_idx = self._find_header_row(table, columns_spec)
        if header_idx >= len(table):
            return {}
        header = [(c or "").strip().lower() for c in table[header_idx]]
        if not any(header):
            return {}
        mapping: dict[str, int] = {}
        for spec in columns_spec:
            pattern = spec.get("matches")
            field_name = spec.get("field")
            if not pattern or not field_name:
                continue
            for col_idx, cell in enumerate(header):
                if cell and re.search(pattern, cell, flags=re.IGNORECASE):
                    mapping[field_name] = col_idx
                    break
        # Require at least two columns matched, else this isn't the table.
        return mapping if len(mapping) >= 2 else {}
