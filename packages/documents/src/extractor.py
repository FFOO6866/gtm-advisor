"""PDF and HTML text extractor with section detection.

Uses pypdf (already in project deps) to extract PDF text.
Uses stdlib html.parser to strip HTML tags for SEC EDGAR filings.
Detects common sections in annual/sustainability reports by scanning
for header-like lines.
Does NOT attempt OCR — scanned/image PDFs will return empty text gracefully.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

import pypdf

# Maximum characters we keep in full_text to avoid blowing up memory.
_FULL_TEXT_CAP = 500_000

# Maximum pages processed per document (skip the rest of very long reports).
_MAX_PAGES = 200

# Average chars/page below this threshold signals a scanned/image PDF.
_SCANNED_THRESHOLD_CHARS_PER_PAGE = 100


# Section headers to detect (case-insensitive substring match on a line).
class _TextStripper(HTMLParser):
    """Minimal HTML-to-text converter using stdlib HTMLParser.

    Strips all tags; collapses whitespace; handles &nbsp; and common entities.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_tags = {"script", "style", "head"}
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: object) -> None:  # noqa: ARG002
        if tag.lower() in self._skip_tags:
            self._skip_depth += 1
        # Insert a line break for block-level tags to preserve sentence boundaries.
        if tag.lower() in {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._skip_tags:
            self._skip_depth = max(0, self._skip_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        # Collapse runs of whitespace/blank lines to at most two newlines
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


SECTION_PATTERNS: dict[str, list[str]] = {
    "Chairman's Message": [
        "chairman",
        "chairman's message",
        "chairman's statement",
        "message from the chairman",
    ],
    "CEO Message": [
        "chief executive",
        "ceo's message",
        "message from the ceo",
        "managing director's message",
    ],
    "Strategy": [
        "strategy",
        "our strategy",
        "strategic priorities",
        "strategic direction",
        "business strategy",
        "corporate strategy",
    ],
    "Business Overview": [
        "business overview",
        "about us",
        "our business",
        "company overview",
    ],
    "Financial Highlights": [
        "financial highlights",
        "financial summary",
        "key financial",
    ],
    "Sustainability": [
        "sustainability",
        "esg",
        "environment social governance",
        "corporate responsibility",
    ],
    "Risk Factors": [
        "risk management",
        "risk factors",
        "principal risks",
        "key risks",
    ],
    "Corporate Governance": [
        "corporate governance",
        "board of directors",
        "governance report",
    ],
    "Operations Review": [
        "operations review",
        "operational review",
        "business review",
    ],
    "Operating Expenses": [
        "operating expenses",
        "operating costs",
        "cost structure",
        "expense breakdown",
    ],
    "Sales and Marketing": [
        "sales and marketing",
        "selling and distribution",
        "marketing expenses",
        "go-to-market",
    ],
    "Research and Development": [
        "research and development",
        "r&d",
        "technology and innovation",
        "product development",
    ],
    "Segment Information": [
        "segment information",
        "operating segments",
        "business segments",
        "revenue by segment",
        "geographic information",
        "revenue by geography",
    ],
    "Management Discussion": [
        "management discussion",
        "management's discussion",
        "md&a",
        "operating and financial review",
    ],
}


@dataclass
class ExtractedSection:
    """A named section extracted from a PDF document."""

    section_name: str  # e.g. "Chairman's Message", "Strategy"
    page_start: int
    page_end: int
    text: str  # full text of this section
    token_estimate: int  # rough estimate: len(text) // 4


@dataclass
class ExtractionResult:
    """Result of a PDF extraction attempt."""

    success: bool
    total_pages: int
    total_chars: int
    sections: list[ExtractedSection] = field(default_factory=list)
    full_text: str = ""  # complete extracted text, capped at 500K chars
    error: str | None = None
    is_scanned: bool = False  # True if <100 chars/page on average (likely image PDF)


class DocumentExtractor:
    """Extracts text and detects sections from PDF documents.

    Behaviour:
    - Uses pypdf (sync) to read each page in order.
    - Detects section headers by scanning lines for case-insensitive pattern matches.
    - Caps output at 500K characters and 200 pages to stay memory-safe.
    - Returns ExtractionResult(success=False) on any error — never raises.
    - Does NOT perform OCR; scanned PDFs return minimal text with is_scanned=True.
    """

    def extract(self, file_path: str) -> ExtractionResult:
        """Extract text and sections from a PDF or HTML file.

        Dispatches to ``extract_html`` for ``.htm``/``.html`` files,
        otherwise uses pypdf for PDFs.

        Args:
            file_path: Absolute path to a document file on disk.

        Returns:
            ExtractionResult. On failure, success=False and error is set.
        """
        if Path(file_path).suffix.lower() in {".htm", ".html"}:
            return self.extract_html(file_path)
        try:
            return self._extract(file_path)
        except Exception as exc:
            return ExtractionResult(
                success=False,
                total_pages=0,
                total_chars=0,
                error=f"Extraction failed: {exc}",
            )

    def extract_html(self, file_path: str) -> ExtractionResult:
        """Extract text and sections from an HTML file (e.g. SEC EDGAR 20-F).

        Strips HTML tags using stdlib HTMLParser; applies the same section
        detection logic used for PDFs.

        Args:
            file_path: Absolute path to an HTML file on disk.

        Returns:
            ExtractionResult. On failure, success=False and error is set.
        """
        try:
            html_bytes = Path(file_path).read_bytes()
            # Try UTF-8 first; fall back to latin-1 (common in older EDGAR filings)
            try:
                html_text = html_bytes.decode("utf-8")
            except UnicodeDecodeError:
                html_text = html_bytes.decode("latin-1")

            stripper = _TextStripper()
            stripper.feed(html_text)
            full_text = stripper.get_text()[:_FULL_TEXT_CAP]

            # Simulate pages: split into ~3000-char page-equivalents for section detection
            page_size = 3000
            page_texts = [
                full_text[i : i + page_size]
                for i in range(0, len(full_text), page_size)
            ]
            total_pages = len(page_texts)

            sections = self._detect_sections(page_texts)

            return ExtractionResult(
                success=True,
                total_pages=total_pages,
                total_chars=len(full_text),
                sections=sections,
                full_text=full_text,
                error=None,
                is_scanned=False,
            )
        except Exception as exc:
            return ExtractionResult(
                success=False,
                total_pages=0,
                total_chars=0,
                error=f"HTML extraction failed: {exc}",
            )

    def _extract(self, file_path: str) -> ExtractionResult:
        """Inner extraction — may raise; caller wraps in try/except."""
        reader = pypdf.PdfReader(file_path)
        total_pages = len(reader.pages)
        pages_to_process = min(total_pages, _MAX_PAGES)

        # --- Per-page text extraction ---
        page_texts: list[str] = []
        for page_index in range(pages_to_process):
            page = reader.pages[page_index]
            text = page.extract_text() or ""
            page_texts.append(text)

        # --- Scanned PDF detection ---
        total_chars = sum(len(t) for t in page_texts)
        avg_chars_per_page = total_chars / pages_to_process if pages_to_process > 0 else 0
        is_scanned = avg_chars_per_page < _SCANNED_THRESHOLD_CHARS_PER_PAGE

        # --- Full text (capped) ---
        raw_full_text = "\n\n".join(page_texts)
        full_text = raw_full_text[:_FULL_TEXT_CAP]

        # --- Section detection ---
        sections = self._detect_sections(page_texts)

        return ExtractionResult(
            success=True,
            total_pages=total_pages,
            total_chars=total_chars,
            sections=sections,
            full_text=full_text,
            error=None,
            is_scanned=is_scanned,
        )

    def _detect_sections(self, page_texts: list[str]) -> list[ExtractedSection]:
        """Scan page texts for section headers and group content into sections.

        Detection strategy:
        - For each page, split into lines and check each line against SECTION_PATTERNS.
        - A line matches if it contains a pattern keyword (case-insensitive) and is
          short enough to be a heading (<=120 chars) and not all-numeric.
        - When a match is found, close the current open section and start a new one.
        - The final open section is closed after the last page.
        """
        sections: list[ExtractedSection] = []

        current_name: str | None = None
        current_page_start: int = 0
        current_text_parts: list[str] = []

        for page_index, page_text in enumerate(page_texts):
            page_num = page_index + 1  # 1-based
            lines = page_text.splitlines()

            for line in lines:
                stripped = line.strip()
                matched_section = _match_section_header(stripped)

                if matched_section and matched_section != current_name:
                    # Close the section that was open
                    if current_name is not None:
                        section_text = "\n".join(current_text_parts).strip()
                        sections.append(
                            ExtractedSection(
                                section_name=current_name,
                                page_start=current_page_start,
                                page_end=page_num,
                                text=section_text,
                                token_estimate=len(section_text) // 4,
                            )
                        )

                    # Open the new section
                    current_name = matched_section
                    current_page_start = page_num
                    current_text_parts = []
                else:
                    current_text_parts.append(line)

        # Close the last open section
        if current_name is not None:
            section_text = "\n".join(current_text_parts).strip()
            sections.append(
                ExtractedSection(
                    section_name=current_name,
                    page_start=current_page_start,
                    page_end=len(page_texts),
                    text=section_text,
                    token_estimate=len(section_text) // 4,
                )
            )

        return sections

    def chunk_section(
        self,
        section: ExtractedSection,
        chunk_size: int = 400,
        overlap: int = 50,
    ) -> list[str]:
        """Split section text into overlapping word-boundary chunks.

        Args:
            section: The extracted section to chunk.
            chunk_size: Target chunk size in tokens (1 token ~= 4 chars).
            overlap: Number of tokens to overlap between consecutive chunks.

        Returns:
            List of chunk strings. Returns an empty list if section.text is empty.
        """
        text = section.text
        if not text:
            return []

        char_chunk = chunk_size * 4

        # Split on whitespace to get words
        words = text.split()
        if not words:
            return []

        chunks: list[str] = []
        start_word = 0

        while start_word < len(words):
            # Accumulate words until we reach char_chunk characters
            char_count = 0
            end_word = start_word
            while end_word < len(words):
                word_len = len(words[end_word]) + 1  # +1 for the space
                if char_count + word_len > char_chunk and end_word > start_word:
                    break
                char_count += word_len
                end_word += 1

            chunk_text = " ".join(words[start_word:end_word])
            chunks.append(chunk_text)

            if end_word >= len(words):
                break

            # Step forward by (chunk_size - overlap) tokens, staying on word boundary
            step_chars = (chunk_size - overlap) * 4
            step_char_count = 0
            step_word = start_word
            while step_word < end_word:
                step_char_count += len(words[step_word]) + 1
                if step_char_count >= step_chars:
                    break
                step_word += 1

            prev_start_word = start_word
            start_word = step_word + 1
            # Guard against infinite loop if overlap >= chunk_size or step is zero
            if start_word <= prev_start_word:
                start_word = end_word

        return chunks


def _match_section_header(line: str) -> str | None:
    """Return the section name if the line matches a known section header, else None.

    Matching rules:
    - Line must be non-empty and <=120 characters (headings are short).
    - Line must not be purely numeric (page numbers, years).
    - Line is checked case-insensitively against each pattern's keywords.
    - Short keywords (<=4 chars, e.g. "r&d", "esg") require word-boundary match
      to avoid false positives on substrings.
    - The keyword must represent a meaningful portion of the line (>=20% of its
      non-whitespace length) to avoid matching incidental mentions in long prose.
    """
    if not line:
        return None
    if len(line) > 120:
        return None
    # Skip purely numeric lines (page numbers, years)
    if line.replace(" ", "").replace(".", "").isdigit():
        return None

    line_lower = line.lower()
    line_stripped_len = len(line.replace(" ", ""))

    for section_name, keywords in SECTION_PATTERNS.items():
        for keyword in keywords:
            if keyword not in line_lower:
                continue
            # Short keywords need word-boundary match to avoid substring hits
            # e.g. "r&d" should not match "standard" or "board"
            if len(keyword) <= 4:
                pattern = r"(?<![a-z])" + re.escape(keyword) + r"(?![a-z])"
                if not re.search(pattern, line_lower):
                    continue
            # Keyword must be a significant portion of the line — headings are
            # mostly the keyword itself, not a long sentence that happens to
            # contain the word "strategy"
            keyword_len = len(keyword.replace(" ", ""))
            if line_stripped_len > 0 and keyword_len / line_stripped_len < 0.20:
                continue
            return section_name

    return None
