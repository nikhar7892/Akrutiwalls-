/**
 * HTTP client for the Python parser sidecar.
 * One internal call: POST /parse with the PDF bytes; returns a structured extract.
 */

const PARSER_URL = process.env.PARSER_SERVICE_URL || "http://localhost:8000";
const PARSER_SECRET = process.env.PARSER_SHARED_SECRET || "";

export type FieldSlot = {
  value: string | number | boolean | null;
  source: "acroform" | "regex" | "default" | "llm" | "ocr";
  confidence: number;
};

export type ParseExtract = {
  [entity: string]: Record<string, FieldSlot> | unknown;
};

export type ParseResponse = {
  matched: boolean;
  playbook: string | null;
  confidence: "high" | "medium" | "low" | "none";
  extracted: ParseExtract;
  raw: {
    filename: string;
    page_count: number;
    text_length: number;
    acroform_fields_found: number;
    tables_found: number;
    ocr_used: boolean;
  };
  warnings: string[];
  needs_llm: boolean;
  llm_used: boolean;
};

export async function callParser(
  filename: string,
  bytes: Buffer,
  mimeType: string | null,
  hintForm?: string | null,
): Promise<ParseResponse> {
  const form = new FormData();
  form.set("file", new Blob([bytes], { type: mimeType || "application/pdf" }), filename);
  if (hintForm) form.set("hint_form", hintForm);

  const res = await fetch(`${PARSER_URL}/parse`, {
    method: "POST",
    body: form,
    headers: PARSER_SECRET ? { "X-Parser-Secret": PARSER_SECRET } : undefined,
    cache: "no-store",
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`parser ${res.status}: ${text.slice(0, 300)}`);
  }
  return (await res.json()) as ParseResponse;
}
