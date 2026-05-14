"""
Akrutiwalls MCA parser service.

A thin FastAPI app that accepts a PDF + optional form hint, runs the playbook
engine (AcroForm reads + regex extractors + transforms), optionally falls back
to an LLM for free-text fields, and returns a structured extract that the
Next.js app shows in its review UI.

Design goals:
- Deterministic-first: zero LLM tokens for MCA portal forms (~95% coverage).
- Domain experts edit YAML playbooks, not code.
- Single internal endpoint; auth via shared secret header.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from parser.engine import PlaybookEngine
from parser.llm import maybe_llm_fill
from parser.pdf import PdfBundle, extract_bundle

SHARED_SECRET = os.getenv("PARSER_SHARED_SECRET", "")
LLM_ENABLED = os.getenv("PARSER_LLM_ENABLED", "false").lower() in ("1", "true", "yes")
PLAYBOOK_DIR = os.getenv("PARSER_PLAYBOOK_DIR", "playbooks")

app = FastAPI(title="Akrutiwalls MCA Parser", version="0.1.0")
engine = PlaybookEngine(PLAYBOOK_DIR)


def _check_auth(secret: Optional[str]) -> None:
    if SHARED_SECRET and secret != SHARED_SECRET:
        raise HTTPException(status_code=401, detail="bad shared secret")


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "playbooks": engine.list_playbooks(),
        "llm_enabled": LLM_ENABLED,
        "ocr_available": True,
    }


@app.get("/playbooks")
def list_playbooks(x_parser_secret: Optional[str] = Header(default=None)) -> list:
    _check_auth(x_parser_secret)
    return engine.describe_playbooks()


@app.post("/parse")
async def parse(
    file: UploadFile = File(...),
    hint_form: Optional[str] = Form(default=None),
    x_parser_secret: Optional[str] = Header(default=None),
) -> JSONResponse:
    _check_auth(x_parser_secret)

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")

    bundle: PdfBundle = extract_bundle(data, filename=file.filename or "upload.pdf")

    match = engine.match(bundle, hint_form=hint_form)
    if not match:
        return JSONResponse({
            "matched": False,
            "playbook": None,
            "confidence": "none",
            "extracted": {},
            "raw": bundle.summary(),
            "warnings": ["no playbook matched; pick a form manually or add a playbook"],
            "needs_llm": False,
            "llm_used": False,
        })

    extracted = engine.run(match, bundle)

    needs_llm, llm_used = False, False
    if LLM_ENABLED and match.llm_hints:
        needs_llm = True
        try:
            extracted = maybe_llm_fill(match, bundle, extracted)
            llm_used = True
        except Exception as exc:  # noqa: BLE001 — never crash the parse on LLM trouble
            extracted.setdefault("_warnings", []).append(f"llm fallback failed: {exc}")

    return JSONResponse({
        "matched": True,
        "playbook": match.form,
        "confidence": engine.confidence_label(extracted),
        "extracted": extracted,
        "raw": bundle.summary(),
        "warnings": extracted.pop("_warnings", []),
        "needs_llm": needs_llm,
        "llm_used": llm_used,
    })
