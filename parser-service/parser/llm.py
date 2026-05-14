"""
LLM fallback — Claude Haiku 4.5.

Used only when a playbook explicitly declares `llm:` hints AND
`PARSER_LLM_ENABLED=true`. We never send the whole document — only the
unresolved fields' schema and a relevant text snippet. Keeps tokens tiny.

Typical use cases:
  - Free-text "purpose" for a non-standard form
  - "What is this BR/EGM resolution about?" → one-sentence gist
  - Sniffing form type from a scanned cover sheet

Output is structured JSON via `output_config.format = json_schema` so the
engine can merge it back into the extract without parsing prose.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from parser.engine import Playbook
from parser.pdf import PdfBundle

log = logging.getLogger(__name__)

MODEL = os.getenv("PARSER_LLM_MODEL", "claude-haiku-4-5")
MAX_TEXT_CHARS = 4000  # ~1000 tokens of context — keeps the call cheap


def maybe_llm_fill(p: Playbook, bundle: PdfBundle, extract: dict) -> dict:
    """If the playbook declares missing fields to ask the LLM about, fill them."""
    hints = p.llm_hints or {}
    fields_spec: dict = hints.get("fields") or {}
    if not fields_spec:
        return extract

    # Only ask about fields that are still empty after rules ran.
    missing: dict[str, dict] = {}
    for path, spec in fields_spec.items():
        entity, field_name = path.split(".", 1) if "." in path else ("_root", path)
        if field_name not in extract.get(entity, {}):
            missing[path] = spec
    if not missing:
        return extract

    import anthropic  # type: ignore

    if not os.getenv("ANTHROPIC_API_KEY"):
        extract.setdefault("_warnings", []).append("LLM enabled but ANTHROPIC_API_KEY not set")
        return extract

    snippet = (bundle.text or "")[:MAX_TEXT_CHARS]
    schema = _build_json_schema(missing)
    system = hints.get("system") or (
        "You are an Indian MCA filings expert. Extract only the requested fields from "
        "the document snippet. Respond strictly in the requested JSON schema. If a "
        "field is genuinely not present, return null for it."
    )

    client = anthropic.Anthropic()
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Form: {p.form}\n"
                        f"Document snippet (may be partial):\n```\n{snippet}\n```\n\n"
                        f"Return JSON with these fields:\n{json.dumps(missing, indent=2)}"
                    ),
                }
            ],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM call failed: %s", exc)
        extract.setdefault("_warnings", []).append(f"LLM call failed: {exc}")
        return extract

    payload = _read_json_response(resp)
    if not isinstance(payload, dict):
        return extract

    for path, value in payload.items():
        if value in (None, ""):
            continue
        entity, field_name = path.split(".", 1) if "." in path else ("_root", path)
        extract.setdefault(entity, {})[field_name] = {
            "value": value,
            "source": "llm",
            "confidence": 0.6,  # always lower than rules — encourages user review
        }
    return extract


def _build_json_schema(missing: dict[str, dict]) -> dict:
    properties: dict[str, dict] = {}
    for path, spec in missing.items():
        properties[path] = {
            "type": ["string", "null"],
            "description": spec.get("description", ""),
        }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys()),
        "additionalProperties": False,
    }


def _read_json_response(resp: Any) -> Any:
    """Pull JSON out of a Messages response regardless of which block carries it."""
    for block in getattr(resp, "content", []) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str) and text.strip().startswith("{"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue
    return None
