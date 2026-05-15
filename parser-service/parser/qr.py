"""
QR-code helper for PAN and Udyam.

Per Stage 2 brief: 'For QR codes on Udyam and PAN, pyzbar is permitted as the
report calls for it. Make QR decoding non-fatal — if decode fails, fall back to
text extraction and log a soft-warn.'

We render every page of the PDF to a PIL image at 200 DPI and try to decode all
QR rectangles found. The output is a list of decoded strings; callers are
responsible for parsing each (e.g., the PAN QR contains a delimited
name+PAN+DOI string per report §2.D).
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable, Union


def decode_qr_codes(pdf_path: Union[str, Path]) -> tuple[list[str], list[str]]:
    """
    Returns (decoded_strings, warnings). warnings is a list of human-readable
    notes for the inconsistencies log when decode failed for any reason.
    Never raises.
    """
    decoded: list[str] = []
    warnings: list[str] = []

    try:
        import pdfplumber
    except Exception as exc:  # pragma: no cover - dep should be installed
        warnings.append(f"pdfplumber unavailable for QR decode: {exc}")
        return decoded, warnings

    try:
        from pyzbar.pyzbar import decode as zbar_decode  # type: ignore
    except Exception as exc:
        # Either pyzbar package missing OR zbar shared lib missing at runtime.
        warnings.append(f"pyzbar unavailable; skipping QR decode: {exc}")
        return decoded, warnings

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                try:
                    pil_img = page.to_image(resolution=200).original
                except Exception as exc:
                    warnings.append(f"Page render failed: {exc}")
                    continue
                try:
                    for item in zbar_decode(pil_img):
                        try:
                            decoded.append(item.data.decode("utf-8", errors="replace"))
                        except Exception as exc:
                            warnings.append(f"QR payload decode failed: {exc}")
                except Exception as exc:
                    warnings.append(f"QR scan failed on page: {exc}")
    except Exception as exc:
        warnings.append(f"PDF open failed for QR decode: {exc}")

    return decoded, warnings
