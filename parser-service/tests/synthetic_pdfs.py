"""
Synthetic-PDF helpers for Stage 2 tests.

Each builder reproduces the report-stated layout for one Group A document
type (just enough text/anchors for the extractor to do its job — not a
visual replica). Identifiers used here are the report's public test
vector (GSTIN 27AAPFU0939F1ZV) plus consistent fictional values for the
other identifiers — re-used across documents to exercise the cross-doc
validation matrix in the E2E test.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable, Sequence

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


# ---- Fictional company used across the E2E suite -------------------------
SAMPLE_CIN = "U72900MH2018PTC123456"   # year 2018, state MH per CIN positions 7-8 / 9-12
# PAN with 4th char 'C' so the PAN-card classifier (which restricts on entity-type
# C per report §2.A — '4th character is always C for a company') recognises it.
SAMPLE_PAN = "AAACD1234E"
SAMPLE_TAN = "BLRA12345B"
# GSTIN computed with valid Luhn-mod-36 check: state '27' + SAMPLE_PAN + entity '1' + 'Z' + check.
# Verified via parser.identifiers.is_valid_gstin.
SAMPLE_GSTIN = "27AAACD1234E1Z9"
SAMPLE_UDYAM = "UDYAM-MH-19-0054448"   # report's Udyam example
SAMPLE_DIN_1 = "00012345"
SAMPLE_DIN_2 = "00098765"
SAMPLE_LEGAL_NAME = "Demo Tech Private Limited"
SAMPLE_DOI_ISO = "2018-04-05"          # year matches CIN positions 9-12
SAMPLE_AUTHORISED_CAPITAL = 1_000_000


def _new_canvas(path: Path) -> canvas.Canvas:
    return canvas.Canvas(str(path), pagesize=A4)


def _draw_lines(c: canvas.Canvas, lines: Iterable[str], y_start: int = 800, leading: int = 14) -> None:
    y = y_start
    for line in lines:
        c.drawString(60, y, line)
        y -= leading
        if y < 60:
            c.showPage()
            y = 800


# ---------------------------------------------------------------------------
# 1. COI (Form INC-11)
# ---------------------------------------------------------------------------

def write_coi(path: Path) -> Path:
    c = _new_canvas(path)
    _draw_lines(c, [
        "Certificate of Incorporation [Pursuant to sub-section (2) of section 7 of the Companies Act, 2013 (18 of 2013) and rule 18 of the Companies (Incorporation) Rules, 2014]",
        f"I hereby certify that {SAMPLE_LEGAL_NAME} is incorporated on this FIFTH day of APRIL two thousand eighteen under the Companies Act, 2013 (18 of 2013) and that the company is limited by shares.",
        f"The Corporate Identity Number (CIN) of the company is {SAMPLE_CIN}.",
        f"The Permanent Account Number (PAN) of the company is {SAMPLE_PAN}.",
        "For and on behalf of the Jurisdictional Registrar of Companies — Central Registration Centre",
        "Assistant Registrar of Companies",
        "Place: Manesar",
    ])
    c.save()
    return path


# ---------------------------------------------------------------------------
# 2. PAN Card (Company)
# ---------------------------------------------------------------------------

def write_pan_card(path: Path) -> Path:
    c = _new_canvas(path)
    _draw_lines(c, [
        "INCOME TAX DEPARTMENT — GOVT. OF INDIA",
        f"Permanent Account Number Card",
        f"PAN: {SAMPLE_PAN}",
        f"Name: {SAMPLE_LEGAL_NAME}",
        f"Date of Incorporation: 05/04/2018",
    ])
    c.save()
    return path


# ---------------------------------------------------------------------------
# 3. TAN Allotment Letter
# ---------------------------------------------------------------------------

def write_tan_letter(path: Path) -> Path:
    c = _new_canvas(path)
    _draw_lines(c, [
        "Income Tax Department — Government of India",
        f"Tax Deduction Account Number (TAN)",
        f"TAN: {SAMPLE_TAN}",
        f"Name of Deductor: {SAMPLE_LEGAL_NAME}",
        f"PAN of Deductor: {SAMPLE_PAN}",
        "Address: 12 MG Road, Bengaluru, Karnataka 560001",
        "Category: Company",
        "AO Code: BLR W 042 1",
        "Form 49B Acknowledgement: 12345678901234",
        "Date of Allotment: 10/05/2018",
    ])
    c.save()
    return path


# ---------------------------------------------------------------------------
# 4. AoA
# ---------------------------------------------------------------------------

def write_aoa(path: Path) -> Path:
    c = _new_canvas(path)
    _draw_lines(c, [
        f"ARTICLES OF ASSOCIATION OF {SAMPLE_LEGAL_NAME}",
        "I. Interpretation",
        "1. In these regulations 'the Act' means the Companies Act, 2013.",
        "II. Share capital and variation of rights",
        "2. Subject to the provisions of section 62 of the Act and these articles, ...",
        "III. Lien",
        "9. The company shall have a first and paramount lien...",
        "XIX. The Seal",
        "The company may have a common seal but it is optional.",
        "XX. Dividends and Reserve",
        "The company in general meeting may declare dividends...",
        "XXIII. Indemnity",
        "Every officer of the company shall be indemnified out of the assets of the company...",
        "Names, addresses, descriptions and occupations of subscribers:",
        "1. John Smith, 12 MG Road Bangalore, Software Engineer, 5000 equity shares",
        "2. Jane Doe, 45 Park St Mumbai, Director, 5000 equity shares",
        "In witness whereof we have hereunto set our respective hands.",
    ])
    c.save()
    return path


# ---------------------------------------------------------------------------
# 5. MoA
# ---------------------------------------------------------------------------

def write_moa(path: Path) -> Path:
    c = _new_canvas(path)
    _draw_lines(c, [
        f"The Companies Act, 2013 — MEMORANDUM OF ASSOCIATION OF {SAMPLE_LEGAL_NAME.upper()}",
        f"I. The name of the Company is {SAMPLE_LEGAL_NAME}.",
        "II. The Registered office of the Company will be situated in the State of Maharashtra.",
        "III. The objects for which the Company is established are:",
        "(A) Main objects to be pursued by the Company on its incorporation:",
        "    To engage in the business of computer programming, IT consultancy and related activities.",
        "(B) Matters incidental or ancillary to the attainment of the above main objects:",
        "    All such powers as are necessary to the attainment of the main objects.",
        "IV. The liability of the members is limited by shares.",
        f"V. The Authorised Share Capital of the Company is Rs. {SAMPLE_AUTHORISED_CAPITAL} divided into 100000 equity shares of Rs. 10 each.",
        "VI. We, the several persons whose names, addresses and descriptions are subscribed below...",
    ])
    c.save()

    # Add a subscription table on the next page so pdfplumber.extract_tables picks it up.
    # reportlab can render a Table flowable; for simplicity we draw a 2-row table by hand.
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4 as _A4
    from reportlab.platypus import SimpleDocTemplate

    # Append the subscription table as a separate page in the same PDF.
    c2 = canvas.Canvas("/tmp/_moa_table_tmp.pdf", pagesize=_A4)
    data = [
        ["Name", "Father's Name", "Address", "Occupation", "Nationality", "DIN/PAN", "No. of Equity Shares Subscribed"],
        ["JOHN SMITH",  "James Smith", "12 MG Rd, Bangalore", "Software Engineer", "Indian", SAMPLE_DIN_1, "5000"],
        ["JANE DOE",    "David Doe",   "45 Park St, Mumbai",  "Director",          "Indian", SAMPLE_DIN_2, "5000"],
    ]
    t = Table(data, colWidths=[60, 60, 95, 65, 50, 60, 100])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    w, h = t.wrap(0, 0)
    t.drawOn(c2, 30, 700)
    c2.save()

    # Merge the two PDFs.
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    for src in (path, "/tmp/_moa_table_tmp.pdf"):
        for page in PdfReader(str(src)).pages:
            writer.add_page(page)
    with open(path, "wb") as fh:
        writer.write(fh)
    return path


# ---------------------------------------------------------------------------
# 6. GST REG-06
# ---------------------------------------------------------------------------

def write_gst_reg_06(path: Path) -> Path:
    c = _new_canvas(path)
    _draw_lines(c, [
        "Form GST REG-06 [See Rule 10(1)] Registration Certificate",
        f"Registration Number: {SAMPLE_GSTIN}",
        "This is a system generated digitally signed Registration Certificate issued based on the approval of application granted on 06/05/2018 by the jurisdictional authority",
        f"1. Legal Name: {SAMPLE_LEGAL_NAME}",
        "2. Trade Name: Demo Tech",
        "3. Additional trade names: None",
        "4. Constitution of Business: Private Limited Company",
        "5. Address of Principal Place of Business: 12 MG Road, Mumbai, Maharashtra 400001",
        "6. Date of Liability: 06/05/2018",
        "7. Period of Validity: Not Applicable",
        "8. Type of Registration: Regular",
        "9. Particulars of Approving Authority: Centre",
        "10. Date of issue of Certificate: 07/05/2018",
        "Note: The registration certificate is required to be prominently displayed at all places of Business/Office(s) in the State.",
    ])
    c.save()

    # Add Annexure A on a second page with a real table.
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    c2 = canvas.Canvas("/tmp/_gst_anx_tmp.pdf", pagesize=A4)
    c2.drawString(60, 800, "Annexure A — Details of Additional Places of Business in the State")
    data_a = [
        ["Sr. No.", "Address"],
        ["1", "Plot 14, Andheri East, Mumbai"],
        ["2", "Wing B, BKC, Mumbai"],
    ]
    t_a = Table(data_a, colWidths=[60, 300])
    t_a.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.black), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
    t_a.wrap(0, 0)
    t_a.drawOn(c2, 60, 700)

    c2.drawString(60, 660, "Annexure B — Details of Proprietor / Partners / Designated Partners")
    data_b = [
        ["Photo", "Name", "Designation", "Resident of State", "Father's Name", "DOB"],
        ["[Photo]", "JOHN SMITH", "Director", "Maharashtra", "James Smith", "01/01/1980"],
    ]
    t_b = Table(data_b, colWidths=[40, 80, 80, 90, 80, 60])
    t_b.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.black), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
    t_b.wrap(0, 0)
    t_b.drawOn(c2, 60, 580)
    c2.save()

    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    for src in (path, "/tmp/_gst_anx_tmp.pdf"):
        for page in PdfReader(str(src)).pages:
            writer.add_page(page)
    with open(path, "wb") as fh:
        writer.write(fh)
    return path


# ---------------------------------------------------------------------------
# 7. Udyam
# ---------------------------------------------------------------------------

def write_udyam(path: Path) -> Path:
    c = _new_canvas(path)
    _draw_lines(c, [
        "Government of India — Ministry of Micro, Small and Medium Enterprises",
        "Udyam Registration Certificate",
        f"Udyam Registration Number: {SAMPLE_UDYAM}",
        f"Name of Enterprise: {SAMPLE_LEGAL_NAME}",
        "Type of Enterprise: Micro",
        "Date of Incorporation/Registration: 05/04/2018",
        "Date of Commencement: 06/05/2018",
        "Major Activity: Services",
        "NIC Code: 62 - Computer programming, consultancy and related activities",
        "NIC Code: 6201 - Computer programming activities",
        "Owner: John Smith, Aadhaar XXXXXXXX1234, Mobile 9876543210, Email john@example.in",
        "Official Address: 12 MG Road, Mumbai 400001",
        "Mobile: 9876543210",
        "Email: contact@demotech.in",
        "Date of Udyam Registration: 12/05/2020",
        f"PAN: {SAMPLE_PAN}",
        f"GSTIN: {SAMPLE_GSTIN}",
    ])
    c.save()
    return path


# ---------------------------------------------------------------------------
# 8. MCA Master Data
# ---------------------------------------------------------------------------

def write_mca_master_data(path: Path) -> Path:
    c = _new_canvas(path)
    _draw_lines(c, [
        "Ministry of Corporate Affairs",
        "Company/LLP Master Data",
        f"CIN: {SAMPLE_CIN}",
        f"Company Name: {SAMPLE_LEGAL_NAME}",
        "RoC-Code: RoC-Mumbai",
        "Registration Number: 312345",
        "Company Category: Company limited by Shares",
        "Company Sub Category: Non-govt company",
        "Class of Company: Private",
        "Date of Incorporation: 05/04/2018",
        "Activity: 62 - Computer programming activities",
        "Address of Registered Office: 12 MG Road, Mumbai 400001, Maharashtra",
        "Email Id: contact@demotech.in",
        "Whether Listed or not: Unlisted",
        "Authorised Capital(Rs): 1000000",
        "Paid up Capital(Rs): 100000",
        "Date of Last AGM: 30/09/2024",
        "Date of Balance Sheet: 31/03/2024",
        "Company Status: Active",
    ])
    c.save()

    # Append the directors / signatory table on a second page so the
    # extractor's table parser can pick it up.
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    c2 = canvas.Canvas("/tmp/_mca_dir_tmp.pdf", pagesize=A4)
    c2.drawString(60, 800, "Directors / Signatory Details")
    data = [
        ["DIN/PAN", "Name", "Designation", "Date of Appointment", "Date of Cessation"],
        [SAMPLE_DIN_1, "JOHN SMITH", "Director", "05/04/2018", ""],
        [SAMPLE_DIN_2, "JANE DOE",   "Director", "05/04/2018", ""],
    ]
    t = Table(data, colWidths=[80, 100, 100, 110, 110])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.black), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
    t.wrap(0, 0)
    t.drawOn(c2, 30, 700)
    c2.save()

    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    for src in (path, "/tmp/_mca_dir_tmp.pdf"):
        for page in PdfReader(str(src)).pages:
            writer.add_page(page)
    with open(path, "wb") as fh:
        writer.write(fh)
    return path


# ---------------------------------------------------------------------------
# Group B — realistic test PDFs for Stage 3 extractor + persistence smoke.
# Distinct SRNs per doc (all matching ^[A-Z][0-9]{8}$).
# ---------------------------------------------------------------------------

SAMPLE_SRN_DIR_12     = "T11000001"
SAMPLE_SRN_MGT_14     = "T22000002"
SAMPLE_SRN_ADT_1      = "T33000003"
SAMPLE_SRN_ADT_3      = "T44000004"
SAMPLE_SRN_DIR_3_KYC  = "T55000005"
SAMPLE_SRN_CHALLAN    = "T66000006"
SAMPLE_SRN_DPT_3      = "T77000007"

SAMPLE_FRN = "012345W"          # FRN ^[0-9]{6}[A-Z]$ per §11.D (TODO sample carried).
SAMPLE_AUDITOR_PAN = "AAACA1234B"  # 4th char 'A' (Firm-of-CAs is allowed; report keeps PAN structure agnostic).


def write_dir_12(path: Path) -> Path:
    """DIR-12 with two repeating director blocks per §9.B/§9.C."""
    c = _new_canvas(path)
    _draw_lines(c, [
        "Ministry of Corporate Affairs",
        "Form No. DIR-12",
        "Particulars of appointment of directors and the key managerial personnel",
        f"CIN: {SAMPLE_CIN}",
        f"Company Name: {SAMPLE_LEGAL_NAME}",
        f"SRN: {SAMPLE_SRN_DIR_12}",
        "Purpose of filing: Appointment",
        "Number of persons: 2",
        "",
        "Particulars of Director [1]",
        f"DIN: {SAMPLE_DIN_1}",
        "Name: JOHN SMITH",
        "Designation: Director",
        "Category: Promoter",
        "DOB: 01/01/1980",
        "Date of appointment: 05/04/2018",
        "",
        "Particulars of Director [2]",
        f"DIN: {SAMPLE_DIN_2}",
        "Name: JANE DOE",
        "Designation: Managing Director",
        "Category: Promoter",
        "DOB: 01/06/1982",
        "Date of appointment: 05/04/2018",
        "",
        "Date of filing: 15/04/2018",
        "Total fee: Rs. 600.00",
    ])
    c.save()
    return path


def write_mgt_14(path: Path) -> Path:
    """MGT-14 with two repeating resolution blocks per §10.B/§10.C."""
    c = _new_canvas(path)
    _draw_lines(c, [
        "Ministry of Corporate Affairs",
        "Form No. MGT-14",
        f"CIN: {SAMPLE_CIN}",
        f"Company Name: {SAMPLE_LEGAL_NAME}",
        f"SRN: {SAMPLE_SRN_MGT_14}",
        "Purpose: Resolution",
        "Number of resolutions: 2",
        "",
        "Resolution [1]",
        "Type: Special",
        "Purpose: Alteration in Articles",
        "Section 14",
        "Date of resolution: 30/09/2023",
        "Place of meeting: Mumbai",
        "",
        "Resolution [2]",
        "Type: Board",
        "Purpose: Borrowing limits",
        "Section 180(1)(c)",
        "Date of resolution: 30/09/2023",
        "Place of meeting: Mumbai",
        "",
        "Date of filing: 25/10/2023",
        "Total fee: Rs. 600.00",
    ])
    c.save()
    return path


def write_adt_1(path: Path) -> Path:
    """ADT-1 with two joint-auditor blocks per §11.B."""
    c = _new_canvas(path)
    _draw_lines(c, [
        "Ministry of Corporate Affairs",
        "Form ADT-1",
        f"CIN: {SAMPLE_CIN}",
        f"Company Name: {SAMPLE_LEGAL_NAME}",
        f"SRN: {SAMPLE_SRN_ADT_1}",
        "Whether Audit Committee recommendation u/s 177 considered: Yes",
        "Nature of appointment: Appointment in AGM",
        "Joint auditors: Yes",
        "Whether appointed in AGM: Yes",
        "Date of AGM: 30/09/2023",
        "Date of appointment: 30/09/2023",
        "",
        "Auditor [1]",
        "Category: Firm",
        f"PAN: {SAMPLE_AUDITOR_PAN}",
        "Name: ACME & Co. LLP",
        f"Firm Registration Number: {SAMPLE_FRN}",
        "Membership No: 123456",
        "Address: 1 MG Road, Mumbai",
        "Email: acme@example.in",
        "Period of account from: 01/04/2023",
        "Period of account to: 31/03/2028",
        "Number of financial years: 5",
        "",
        "Auditor [2]",
        "Category: Individual",
        "PAN: AAAPB1234C",
        "Name: Rakesh Mehta",
        "Membership No: 098765",
        "Address: 4 BKC, Mumbai",
        "Email: rakesh@example.in",
        "Period of account from: 01/04/2023",
        "Period of account to: 31/03/2024",
        "Number of financial years: 1",
        "",
        "Date of filing: 14/10/2023",
        "Total fee: Rs. 600.00",
    ])
    c.save()
    return path


def write_adt_3(path: Path) -> Path:
    """ADT-3 — auditor resignation, links via SRN of original ADT-1 per §12.B field 11."""
    c = _new_canvas(path)
    _draw_lines(c, [
        "Ministry of Corporate Affairs",
        "Form No. ADT-3",
        f"CIN: {SAMPLE_CIN}",
        f"Company Name: {SAMPLE_LEGAL_NAME}",
        f"SRN: {SAMPLE_SRN_ADT_3}",
        "Category of auditor: Firm",
        f"PAN: {SAMPLE_AUDITOR_PAN}",
        "Name of auditor: ACME & Co. LLP",
        f"Firm Registration Number: {SAMPLE_FRN}",
        "Membership Number: 123456",
        "Address of auditor: 1 MG Road, Mumbai",
        "Email: acme@example.in",
        "Date of appointment: 30/09/2023",
        "Date of resignation: 15/03/2024",
        f"SRN of original ADT-1: {SAMPLE_SRN_ADT_1}",
        "Reasons for resignation: Auditor pre-occupied with other engagements.",
    ])
    c.save()
    return path


def write_dir_3_kyc(path: Path, *, din: str = SAMPLE_DIN_1,
                    filed_on: str = "30/06/2024") -> Path:
    """DIR-3 KYC. Filing date before 2026-03-31 → next due 2028-06-30 (S3-R2)."""
    c = _new_canvas(path)
    _draw_lines(c, [
        "Ministry of Corporate Affairs",
        "Form DIR-3 KYC",
        f"CIN: {SAMPLE_CIN}",
        f"SRN: {SAMPLE_SRN_DIR_3_KYC}",
        f"DIN: {din}",
        "Purpose of filing: KYC compliances",
        "Name: JOHN SMITH",
        "Father's name: James Smith",
        "Nationality: Indian",
        "Whether citizen of India: Yes",
        "Whether resident in India: Yes",
        "DOB: 01/01/1980",
        "Gender: Male",
        f"PAN: {SAMPLE_PAN}",
        "Whether has Aadhaar: Yes",
        "Aadhaar Number: XXXXXXXX1234",
        "Mobile: 9876543210",
        "Email: john@example.in",
        "Permanent residential address: 12 MG Road, Bengaluru 560001",
        "Whether present residence same as permanent: Yes",
        f"Date of filing: {filed_on}",
    ])
    c.save()
    return path


def write_srn_challan(path: Path) -> Path:
    """SRN Challan / payment receipt per §14.B."""
    c = _new_canvas(path)
    _draw_lines(c, [
        f"SRN: {SAMPLE_SRN_CHALLAN}",
        "Ministry of Corporate Affairs — Government of India",
        "Service Request Receipt",
        "Service Description: Form DIR-12",
        f"CIN: {SAMPLE_CIN}",
        f"Company Name: {SAMPLE_LEGAL_NAME}",
        "User Name: Akruti Partners LLP",
        "Date of Generation: 15/04/2018",
        "Filing fee: Rs. 600.00",
        "Stamp duty: Rs. 0.00",
        "Additional fee: Rs. 0.00",
        "Total: Rs. 600.00",
        "Mode of payment: Net Banking",
        "Payment status: Paid",
        "Transaction ID: TX1234567890",
        "Bank Name: HDFC Bank",
    ])
    c.save()
    return path


def write_dpt_3(path: Path, *, fy: str = "2023-24") -> Path:
    """DPT-3 with Rule 2(1)(c) sub-clause iteration per §15.B field 12."""
    c = _new_canvas(path)
    _draw_lines(c, [
        "Ministry of Corporate Affairs",
        "Form No. DPT-3",
        f"CIN: {SAMPLE_CIN}",
        f"Company Name: {SAMPLE_LEGAL_NAME}",
        f"SRN: {SAMPLE_SRN_DPT_3}",
        "Type of company: Private",
        "Purpose of filing: Annual Return of deposits",
        "Objects of company: Computer programming and IT consultancy.",
        f"Period for which return is filed: {fy}",
        "Date of last closing of accounts: 31/03/2024",
        "Net Worth: 5000000",
        "Credit rating agency: CRISIL",
        "Credit rating: AA-",
        "Total number of deposit holders: 0",
        "Outstanding Secured: 0",
        "Outstanding Unsecured: 1000000",
        "Outstanding non-deposit: 1500000",
        "",
        "Particulars of receipts not considered as deposits under Rule 2(1)(c):",
        "(i) CG/SG/Local/Statutory Authority: 0",
        "(ii) foreign banks/govt: 0",
        "(iii) banking company: 500000",
        "(iv) loan from bank/FI/insurance: 500000",
        "(v) loan from director/relative (Private Co.): 1000000",
        "(vi) commercial paper: 0",
        "(vii) ICDs: 0",
        "(viii) startup convertible note ≥ ₹25L single tranche: 0",
        "(ix) subscription pending allotment ≤ 60 days: 0",
        "(x) security deposit from employee ≤ annual salary: 0",
        "(xi) customer advance: 0",
        "(xii) ECB: 0",
        "(xiii) others: 0",
        "",
        "Date of filing: 30/06/2024",
        "Total fee: Rs. 600.00",
    ])
    c.save()
    return path
