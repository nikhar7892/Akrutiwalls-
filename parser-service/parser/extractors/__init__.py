"""
Group A document extractors. One module per document type, each exporting a
single ``extract(pdf_path) -> dict`` function returning a chunked payload
keyed by target table name. The persistence layer (``parser.persistence``)
walks those keys and writes to the matching ``parser_*`` tables.
"""
from __future__ import annotations

from importlib import import_module
from typing import Callable

from parser.classifier import DocType


# Group A extractor registry — keys MUST be in DocType.
# Stage 3 will append the Group B registrations to this map.
_GROUP_A_MODULES: dict[DocType, str] = {
    DocType.COI:               "parser.extractors.coi",
    DocType.PAN_CARD:          "parser.extractors.pan_card",
    DocType.TAN_LETTER:        "parser.extractors.tan_letter",
    DocType.AOA:               "parser.extractors.aoa",
    DocType.MOA:               "parser.extractors.moa",
    DocType.GST_REG_06:        "parser.extractors.gst_reg_06",
    DocType.UDYAM:             "parser.extractors.udyam",
    DocType.MCA_MASTER_DATA:   "parser.extractors.mca_master_data",
}


def get_extractor(doc_type: DocType) -> Callable[[str], dict]:
    """Resolve an ``extract(pdf_path)`` callable for the given doc type."""
    module_name = _GROUP_A_MODULES.get(doc_type)
    if not module_name:
        raise ValueError(f"No Stage 2 extractor for {doc_type}")
    module = import_module(module_name)
    return getattr(module, "extract")


def supported_doc_types() -> list[DocType]:
    return list(_GROUP_A_MODULES.keys())
