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

        # 3. Defaults — fill anything still empty
        for target, value in p.defaults.items():
            if self._has(extract, target):
                continue
            self._set(extract, target, value, source="default", confidence=0.7)

        # 4. Final transform pass for AcroForm values (regex already transformed inline)
        for entity, fields_ in extract.items():
            for field_name, slot in fields_.items():
                if slot["source"] == "acroform":
                    # Allow per-target transforms via writes_to.transforms if present.
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
