"""
DSC signer-name extraction.

Per Stage 2 brief: 'pikepdf / endesive for DSC verification on documents that
have a digital signature (COI, GST REG-06, MCA filings)'.

Per report §1.D for COI: 'Extract DSC signer name via pikepdf / endesive.'

We use pikepdf only — the Stage 2 ask is "extract signer name", not full
signature validation. pikepdf can read the PDF /AcroForm/Sig field. Make
this fully non-fatal — any error returns None plus a warning string.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union


def extract_signer_name(pdf_path: Union[str, Path]) -> tuple[Optional[str], list[str]]:
    """
    Returns (signer_name, warnings). signer_name is None when no signature is
    present or extraction failed. warnings carry the failure reason for the
    inconsistencies log.
    """
    warnings: list[str] = []
    try:
        import pikepdf  # type: ignore
    except Exception as exc:
        warnings.append(f"pikepdf unavailable: {exc}")
        return None, warnings

    try:
        with pikepdf.open(str(pdf_path)) as pdf:
            # Walk /AcroForm /Fields looking for /FT /Sig signature field with /V /Name
            try:
                acroform = pdf.Root.AcroForm  # type: ignore[attr-defined]
            except (AttributeError, KeyError):
                return None, warnings
            try:
                fields = acroform.Fields
            except (AttributeError, KeyError):
                return None, warnings
            for f in fields:
                try:
                    if str(f.get("/FT", "")) != "/Sig":
                        continue
                    sig = f.get("/V", None)
                    if sig is None:
                        continue
                    name = sig.get("/Name", None)
                    if name is not None:
                        return str(name), warnings
                except Exception as exc:
                    warnings.append(f"DSC field walk error: {exc}")
                    continue
    except Exception as exc:
        warnings.append(f"DSC extraction failed: {exc}")
    return None, warnings
