# Akrutiwalls MCA — Parser Service

A small FastAPI service that extracts structured data from MCA forms
(INC-22, DIR-12, SH-7, PAS-3, AOC-4, MGT-7, challans, …) so the Next.js
app can pre-fill the master with one click instead of manual data entry.

## Why deterministic, not LLM-first

MCA portal-generated PDFs almost always ship with **AcroForm fields** — the
form values are embedded by name, so we read them directly: zero LLM
tokens, ~100% accuracy. For the rest (text-only fields, dates, SRNs,
amounts) we use **regex rules per form**, declared in YAML.

The LLM (Claude Haiku 4.5) is opt-in and only used to:
1. Fill genuinely free-text fields (e.g. "what is this BR / EGM about?")
2. Clean up OCR output from scanned attachments
3. Sniff the form type when the user uploads without picking one

Estimated cost at typical CA firm volume (a few thousand docs/year):
**under ₹100/year**.

## How a playbook works

Each form has one YAML in `playbooks/`. Example (trimmed):

```yaml
form: INC-22
description: Notice of situation or change of registered office

match:
  text_contains: ["Form No. INC-22"]

acroform:
  CIN: company.cin
  RegisteredOfficeAddressLine1: address.line1
  EffectiveDate: address.effectiveFrom

regex:
  - field: filing.srn
    pattern: 'SRN[\s:]+([A-Z]\d{8})'
  - field: filing.amountPaid
    pattern: '(?:Fee|Amount)[\s:Rs.₹]*([\d,]+(?:\.\d{1,2})?)'
    transform: number

defaults:
  filing.form: "INC-22"
  address.type: "REGISTERED"

writes_to:
  - entity: Address
    requires: [line1, city, state, pin, effectiveFrom]
  - entity: Filing
    requires: [form]
```

The engine:
1. Reads the PDF (AcroForm + text + tables; OCR if no text).
2. Picks the matching playbook (`match.text_contains` / filename / hint).
3. Runs AcroForm map → regex map → defaults, in that order.
4. Returns `{entity: {field: {value, source, confidence}}}` — the
   Next.js review UI shows each field with its source so the CA can
   accept / edit / reject before anything writes to the master.

Adding a new form = adding one YAML. No code changes.

## Field paths

Use `entity.field` dotted paths. The engine recognises these entities:

| Entity              | Notes                                       |
| ------------------- | ------------------------------------------- |
| `company`           | Identity (CIN, name, PAN, …)                |
| `address`           | Registered/corporate address                |
| `capital`           | CapitalHistory snapshot                     |
| `director`          | Director master (DIN-keyed)                 |
| `directorship`      | Company×Director relation                   |
| `shareholder`       | Shareholder master                          |
| `shareholding`      | ShareholdingEntry (ledger row)              |
| `filing`            | MCA filing log (form, SRN, amount, purpose) |

## Transforms

Per-rule `transform:` value:
- `date` — parses Indian date formats → ISO `YYYY-MM-DD`.
- `number` — strips `₹`, `Rs.`, commas → float.
- `int` — same as `number`, then `int()`.
- `upper` — uppercase + trim.
- `fy` — normalize to `YYYY-YY` (e.g. `2023-24`).

## Running

```bash
cd parser-service
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

```bash
# Sanity check
curl http://localhost:8000/health

# Parse a PDF
curl -F "file=@inc22-sample.pdf" \
     -H "X-Parser-Secret: $PARSER_SHARED_SECRET" \
     http://localhost:8000/parse | jq
```

Docker compose runs it alongside the app — see top-level `docker-compose.yml`.

## Environment

| Var | Default | Description |
| --- | --- | --- |
| `PARSER_SHARED_SECRET` | "" (off) | If set, all auth'd routes require `X-Parser-Secret`. |
| `PARSER_LLM_ENABLED` | `false` | Turn on Haiku fallback. Requires `ANTHROPIC_API_KEY`. |
| `PARSER_LLM_MODEL` | `claude-haiku-4-5` | Override the LLM model. |
| `ANTHROPIC_API_KEY` | — | Anthropic key for the Haiku fallback. |
| `PARSER_PLAYBOOK_DIR` | `playbooks` | Where playbook YAMLs live. |
