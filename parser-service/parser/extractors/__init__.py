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


# Extractor registry — keys MUST be in DocType. Stage 2 covered Group A
# (rows 1-8). Stage 3 appends Group B (rows 9-15). Same module signature
# for both: ``extract(pdf_path) -> dict``.
_DOC_MODULES: dict[DocType, str] = {
    # Group A — Stage 2
    DocType.COI:               "parser.extractors.coi",
    DocType.PAN_CARD:          "parser.extractors.pan_card",
    DocType.TAN_LETTER:        "parser.extractors.tan_letter",
    DocType.AOA:               "parser.extractors.aoa",
    DocType.MOA:               "parser.extractors.moa",
    DocType.GST_REG_06:        "parser.extractors.gst_reg_06",
    DocType.UDYAM:             "parser.extractors.udyam",
    DocType.MCA_MASTER_DATA:   "parser.extractors.mca_master_data",
    # Group B — Stage 3
    DocType.DIR_12:            "parser.extractors.dir_12",
    DocType.MGT_14:            "parser.extractors.mgt_14",
    DocType.ADT_1:             "parser.extractors.adt_1",
    DocType.ADT_3:             "parser.extractors.adt_3",
    DocType.DIR_3_KYC:         "parser.extractors.dir_3_kyc",
    DocType.SRN_CHALLAN:       "parser.extractors.srn_challan",
    DocType.DPT_3:             "parser.extractors.dpt_3",
}

# Backwards-compatibility alias used by earlier Stage 2 code paths.
_GROUP_A_MODULES = _DOC_MODULES


def get_extractor(doc_type: DocType) -> Callable[[str], dict]:
    """Resolve an ``extract(pdf_path)`` callable for the given doc type."""
    module_name = _DOC_MODULES.get(doc_type)
    if not module_name:
        raise ValueError(f"No extractor registered for {doc_type}")
    module = import_module(module_name)
    return getattr(module, "extract")


def supported_doc_types() -> list[DocType]:
    return list(_DOC_MODULES.keys())
