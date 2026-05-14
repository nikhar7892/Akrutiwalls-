"""PDF extraction: AcroForm fields, full text, tables. OCR fallback for scans."""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Optional

import pdfplumber
import pypdf

log = logging.getLogger(__name__)


@dataclass
class PdfBundle:
    filename: str
    text: str
    acroform: dict[str, str] = field(default_factory=dict)
    tables: list[list[list[Optional[str]]]] = field(default_factory=list)
    page_count: int = 0
    ocr_used: bool = False

    def summary(self) -> dict:
        return {
            "filename": self.filename,
            "page_count": self.page_count,
            "text_length": len(self.text),
            "acroform_fields_found": len(self.acroform),
            "tables_found": len(self.tables),
            "ocr_used": self.ocr_used,
        }


def extract_bundle(data: bytes, filename: str = "upload.pdf") -> PdfBundle:
    bundle = PdfBundle(filename=filename, text="")
    bundle.acroform = _read_acroform(data)
    bundle.text, bundle.tables, bundle.page_count = _read_text_and_tables(data)

    if len(bundle.text.strip()) < 40 and bundle.page_count > 0:
        # Likely a scanned PDF — try OCR.
        try:
            ocr_text = _ocr_pdf(data)
            if ocr_text and len(ocr_text.strip()) > len(bundle.text.strip()):
                bundle.text = ocr_text
                bundle.ocr_used = True
        except Exception as exc:  # noqa: BLE001
            log.warning("OCR fallback failed: %s", exc)

    return bundle


def _read_acroform(data: bytes) -> dict[str, str]:
    """Extract AcroForm fields by name. MCA-portal PDFs usually have these."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        raw = reader.get_form_text_fields() or {}
        return {k: (v or "").strip() for k, v in raw.items() if v is not None}
    except Exception as exc:  # noqa: BLE001
        log.warning("AcroForm read failed: %s", exc)
        return {}


def _read_text_and_tables(data: bytes) -> tuple[str, list, int]:
    text_parts: list[str] = []
    tables: list[list[list[Optional[str]]]] = []
    page_count = 0
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text:
                    text_parts.append(page_text)
                for tbl in page.extract_tables() or []:
                    tables.append(tbl)
    except Exception as exc:  # noqa: BLE001
        log.warning("pdfplumber failed: %s", exc)
    return "\n".join(text_parts), tables, page_count


def _ocr_pdf(data: bytes) -> str:
    """OCR every page using Tesseract. Slow; only called when text extraction is empty."""
    try:
        import pytesseract
    except ImportError:
        return ""

    text_parts: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                img = page.to_image(resolution=200).original
                text_parts.append(pytesseract.image_to_string(img))
    except Exception as exc:  # noqa: BLE001
        log.warning("OCR pass failed: %s", exc)
    return "\n".join(text_parts)
