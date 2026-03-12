"""Document parsing — extract company profile fields from uploaded files.

Accepts PDF or plain-text files (max 10 MB). Extracts raw text, then uses
GPT-4o-mini with temperature=0 and a strict "extract only, do not invent"
system prompt to return structured company-profile fields.

Edge cases handled:
  - Image-only / scanned PDFs   → 422 with clear message
  - Spoofed file type           → validated by actually parsing, not MIME
  - Very long documents         → text truncated to MAX_TEXT_CHARS before LLM
  - LLM extraction failure      → 502 with advice to fill manually
  - Empty / corrupt files       → 400 / 422 with explanation
"""

from __future__ import annotations

import io
import json
from typing import Any

import structlog
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

MAX_FILE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_TEXT_CHARS = 100_000             # ~25 k tokens — GPT-4o handles up to 128 k

VALID_INDUSTRIES = {
    "fintech", "saas", "ecommerce", "healthcare",
    "logistics", "professional_services", "education", "other",
}

SYSTEM_PROMPT = """\
You are an independent business analyst preparing a company profile brief for a GTM strategy
engagement. The uploaded document was written BY the company (website copy, pitch deck, or
business plan). It may use first-person ("we deliver…") or second-person marketing language
("transform your business…"). IMPORTANT: in marketing copy "your" and "you" refer to the
document company's CLIENTS, not to the company itself.

Your task: extract factual information ABOUT the company and write it in clear, neutral,
third-person analytical language. Never copy marketing taglines verbatim.

Return ONLY a valid JSON object with exactly these keys:

{
  "company_name": <string or null — the company's trading name>,

  "description": <string or null — 2-4 sentences covering: (1) what the company does,
    (2) who its customers are, (3) how it delivers its service or product, as stated in
    the document. Use neutral, factual language — no superlatives. Do not include
    outcomes the company promises to clients; describe the company's own offering.
    Example for a professional services firm: "Meridian Advisory is a growth consultancy
    that helps mid-market technology companies enter new geographic markets. It provides
    embedded teams of market strategists and sales specialists who work alongside client
    leadership to design and execute market entry plans.">,

  "industry": <one of: "fintech" | "saas" | "ecommerce" | "healthcare" | "logistics"
    | "professional_services" | "education" | "other" — or null if unclear>,

  "value_proposition": <string or null — one sentence describing the core benefit the
    company delivers to its customers, as stated or demonstrated in the document.
    Write as an analyst observation: state what the company does and the outcome for
    clients. Do NOT use "you/your/we/our".
    Example: "Meridian Advisory enables technology companies to compress their market
    entry timeline by providing on-the-ground commercial expertise in target markets.">,

  "goals": <string array, max 5 — the company's own stated business or growth objectives,
    exactly as the document describes them for the company itself (not promises to clients).
    Include both quantitative targets and directional objectives if present.
    Empty array if no goals are explicitly stated for the company.>,

  "challenges": <string array, max 5 — obstacles the company explicitly acknowledges
    it faces: competitive pressure, market conditions, operational constraints, etc.
    Only include challenges the document directly states. Empty array if none stated.>,

  "competitors": <string array, max 5 — names of competing companies or products
    explicitly mentioned in the document. Empty array if none are named.>,

  "target_markets": <string array — geographic markets (countries or regions) the company
    serves or plans to enter, as stated in the document. Empty array if not specified.>
}

CRITICAL RULES:
- Never use first-person ("we", "our") or second-person ("you", "your") in any text output.
- Only include facts explicitly stated in the document — do not infer or invent anything.
- Describe what the company offers; do not list what it promises clients will achieve.
- If a field cannot be determined from the document, return null (strings) or [] (arrays).
- Return only the JSON object — no preamble, no markdown, no explanation.
"""


# ─── Response model ────────────────────────────────────────────────────────

class ParsedCompanyProfile(BaseModel):
    company_name: str | None = None
    description: str | None = None
    industry: str | None = None
    value_proposition: str | None = None
    goals: list[str] = []
    challenges: list[str] = []
    competitors: list[str] = []
    target_markets: list[str] = []
    extracted_chars: int = 0
    extracted_text: str | None = None  # Truncated text sent to LLM, for agent context
    warning: str | None = None


# ─── Text extraction helpers ───────────────────────────────────────────────

def _extract_pdf(data: bytes) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(data))
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
        return "\n".join(pages)
    except Exception as exc:
        raise ValueError(f"Could not read PDF: {exc}") from exc


def _extract_docx(data: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(data))
        parts: list[str] = []
        for para in doc.paragraphs:
            if para.text.strip():
                parts.append(para.text)
        # Also pull text from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        parts.append(cell.text)
        return "\n".join(parts)
    except Exception as exc:
        raise ValueError(f"Could not read DOCX: {exc}") from exc


def _extract_txt(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode text file — unsupported character encoding.")


def _extract_text(data: bytes, filename: str, content_type: str) -> str:
    fn = filename.lower()
    ct = content_type.lower()

    if fn.endswith(".pdf") or "pdf" in ct:
        return _extract_pdf(data)

    if fn.endswith(".docx") or "wordprocessingml" in ct or "msword" in ct:
        return _extract_docx(data)

    if fn.endswith(".txt") or "text/plain" in ct:
        return _extract_txt(data)

    # Unknown extension — try PDF, then DOCX, then plain text
    for extractor in (_extract_pdf, _extract_docx, _extract_txt):
        try:
            return extractor(data)
        except ValueError:
            continue
    raise ValueError("Could not extract text from this file. Please use PDF, DOCX, or TXT.")


# ─── Output coercion ───────────────────────────────────────────────────────

def _to_str_list(value: Any) -> list[str]:
    """Coerce LLM output to list[str], guarding against wrong types."""
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value.strip():
        # Model returned a delimited string instead of an array.
        # Prefer newline splitting (common for numbered lists); fall back to comma.
        sep = "\n" if "\n" in value else ","
        return [item.strip() for item in value.split(sep) if item.strip()]
    return []


# ─── LLM extraction ────────────────────────────────────────────────────────

async def _llm_extract(text: str) -> dict[str, Any]:
    """Call GPT-4o-mini with structured output to extract company fields."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Document:\n\n{text[:MAX_TEXT_CHARS]}"},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=1500,
    )
    raw = response.choices[0].message.content or "{}"
    return json.loads(raw)


# ─── Endpoint ──────────────────────────────────────────────────────────────

@router.post("/parse", response_model=ParsedCompanyProfile)
async def parse_document(file: UploadFile = File(...)) -> ParsedCompanyProfile:
    """
    Extract structured company profile fields from an uploaded PDF or text file.

    - Max 10 MB
    - Accepts .pdf and .txt
    - Returns null for fields that cannot be determined from the document
    """
    # 1. Read + size guard
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="File is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_BYTES // 1_048_576} MB.",
        )

    # 2. Extract text
    try:
        raw_text = _extract_text(
            data,
            filename=file.filename or "",
            content_type=file.content_type or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    stripped = raw_text.strip()
    if not stripped:
        raise HTTPException(
            status_code=422,
            detail=(
                "No readable text found in this document. "
                "If it's a scanned PDF, please type or paste the content instead."
            ),
        )

    logger.info(
        "document_parse_requested",
        filename=file.filename,
        chars=len(stripped),
    )

    # 3. LLM extraction
    try:
        extracted = await _llm_extract(stripped)
    except Exception as exc:
        logger.warning("document_llm_extraction_failed", error=str(exc))
        raise HTTPException(
            status_code=502,
            detail=(
                f"AI extraction failed ({exc}). "
                "Please fill in the details manually or try a different file."
            ),
        ) from exc

    # 4. Sanitise industry value
    industry = extracted.get("industry")
    if industry and industry not in VALID_INDUSTRIES:
        industry = "other"

    warning = None
    if len(stripped) > MAX_TEXT_CHARS:
        warning = (
            f"Document is long ({len(stripped):,} characters). "
            f"Only the first {MAX_TEXT_CHARS:,} characters were analysed."
        )

    try:
        return ParsedCompanyProfile(
            company_name=extracted.get("company_name") or None,
            description=extracted.get("description") or None,
            industry=industry,
            value_proposition=extracted.get("value_proposition") or None,
            goals=_to_str_list(extracted.get("goals")),
            challenges=_to_str_list(extracted.get("challenges")),
            competitors=_to_str_list(extracted.get("competitors")),
            target_markets=_to_str_list(extracted.get("target_markets")),
            extracted_chars=len(stripped),
            extracted_text=stripped[:MAX_TEXT_CHARS],
            warning=warning,
        )
    except Exception as exc:
        logger.warning("document_profile_construction_failed", error=str(exc))
        raise HTTPException(
            status_code=502,
            detail="AI returned an unexpected response format. Please fill in the details manually.",
        ) from exc
