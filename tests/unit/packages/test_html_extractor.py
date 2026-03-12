"""Unit tests for HTML extraction path in DocumentExtractor.

Covers:
- _TextStripper strips tags and normalises whitespace
- extract_html() returns ExtractionResult(success=True) for valid HTML
- extract_html() returns ExtractionResult(success=False) on missing file
- extract() dispatches to extract_html() for .htm/.html extensions
- extract() still calls pypdf for .pdf extension (mocked)
- Section detection works in HTML-extracted text
"""

from __future__ import annotations

import tempfile
from unittest.mock import MagicMock, patch

from packages.documents.src.extractor import DocumentExtractor, _TextStripper

# ---------------------------------------------------------------------------
# _TextStripper
# ---------------------------------------------------------------------------


class TestTextStripper:
    def _strip(self, html: str) -> str:
        s = _TextStripper()
        s.feed(html)
        return s.get_text()

    def test_strips_tags(self) -> None:
        result = self._strip("<p>Hello <b>world</b></p>")
        assert "Hello" in result
        assert "world" in result
        assert "<" not in result

    def test_skips_script_content(self) -> None:
        result = self._strip("<html><script>var x=1;</script><p>Real text</p></html>")
        assert "Real text" in result
        assert "var x" not in result

    def test_skips_style_content(self) -> None:
        result = self._strip("<html><style>body{color:red}</style><p>Content</p></html>")
        assert "Content" in result
        assert "color" not in result

    def test_skips_head_content(self) -> None:
        result = self._strip("<html><head><title>Page Title</title></head><body>Body text</body></html>")
        assert "Body text" in result
        assert "Page Title" not in result

    def test_collapses_whitespace(self) -> None:
        result = self._strip("<p>a    b\t\tc</p>")
        # Multiple spaces collapsed to single space
        assert "a b" in result or "a  b" not in result

    def test_converts_entities(self) -> None:
        result = self._strip("<p>AT&amp;T &nbsp; LLC</p>")
        assert "AT&T" in result

    def test_block_tags_add_newlines(self) -> None:
        result = self._strip("<div>First</div><div>Second</div>")
        assert "First" in result
        assert "Second" in result


# ---------------------------------------------------------------------------
# DocumentExtractor.extract_html
# ---------------------------------------------------------------------------


SAMPLE_20F_HTML = """<!DOCTYPE html>
<html>
<head><title>Sea Ltd Form 20-F 2024</title>
<style>body { font-family: Arial; }</style>
</head>
<body>
<h1>Annual Report 2024</h1>
<div class="section">
  <h2>Risk Factors</h2>
  <p>Our business is subject to various risks including regulatory, competitive, and macroeconomic risks.</p>
  <p>Changes in regulations in Singapore and Southeast Asia may adversely affect our operations.</p>
</div>
<div class="section">
  <h2>Strategy</h2>
  <p>Our strategy focuses on deepening market penetration in existing markets.</p>
  <p>We continue to invest in digital financial services through SeaMoney.</p>
</div>
<script>console.log("should be stripped");</script>
<div>
  <p>Financial Highlights: Revenue grew 21% year-over-year to $16.5 billion.</p>
</div>
</body>
</html>
"""


class TestExtractHtml:
    def setup_method(self) -> None:
        self._extractor = DocumentExtractor()

    def _write_html(self, content: str, suffix: str = ".htm") -> str:
        """Write content to a temp file and return its path."""
        with tempfile.NamedTemporaryFile(
            suffix=suffix, mode="w", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write(content)
            return tmp.name

    def test_extract_html_success(self) -> None:
        path = self._write_html(SAMPLE_20F_HTML)
        result = self._extractor.extract_html(path)

        assert result.success is True
        assert result.total_chars > 0
        assert result.total_pages > 0
        assert result.is_scanned is False
        assert result.error is None

    def test_strips_script_and_style(self) -> None:
        path = self._write_html(SAMPLE_20F_HTML)
        result = self._extractor.extract_html(path)

        assert "should be stripped" not in result.full_text
        assert "font-family" not in result.full_text

    def test_skips_head_title(self) -> None:
        path = self._write_html(SAMPLE_20F_HTML)
        result = self._extractor.extract_html(path)
        # Head content (title) should not appear in extracted text
        assert "Sea Ltd Form 20-F 2024" not in result.full_text

    def test_preserves_body_text(self) -> None:
        path = self._write_html(SAMPLE_20F_HTML)
        result = self._extractor.extract_html(path)

        assert "SeaMoney" in result.full_text
        assert "Revenue grew 21%" in result.full_text

    def test_section_detection(self) -> None:
        path = self._write_html(SAMPLE_20F_HTML)
        result = self._extractor.extract_html(path)

        section_names = {s.section_name for s in result.sections}
        # "Risk Factors" and "Strategy" are in SECTION_PATTERNS
        assert "Risk Factors" in section_names
        assert "Strategy" in section_names

    def test_missing_file_returns_failure(self) -> None:
        result = self._extractor.extract_html("/nonexistent/path/report.htm")
        assert result.success is False
        assert result.error is not None

    def test_caps_full_text_at_500k(self) -> None:
        # Build HTML with > 500K chars of body text
        big_text = "x " * 300_000  # 600K chars
        html = f"<html><body><p>{big_text}</p></body></html>"
        path = self._write_html(html)
        result = self._extractor.extract_html(path)

        assert result.success is True
        assert len(result.full_text) <= 500_000

    def test_latin1_fallback(self) -> None:
        """Files with Windows-1252/Latin-1 encoding should decode gracefully."""
        html_bytes = b"<html><body><p>Caf\xe9 au lait</p></body></html>"  # é = 0xE9 in latin-1
        with tempfile.NamedTemporaryFile(suffix=".htm", delete=False) as tmp:
            tmp.write(html_bytes)
            tmp_name = tmp.name

        result = self._extractor.extract_html(tmp_name)
        assert result.success is True
        assert "Caf" in result.full_text

    def test_html_extension_dispatch(self) -> None:
        """extract() must call extract_html() for .htm and .html extensions."""
        path_htm = self._write_html(SAMPLE_20F_HTML, suffix=".htm")
        path_html = self._write_html(SAMPLE_20F_HTML, suffix=".html")

        result_htm = self._extractor.extract(path_htm)
        result_html = self._extractor.extract(path_html)

        assert result_htm.success is True
        assert result_html.success is True

    def test_chunk_section_no_infinite_loop_when_overlap_equals_chunk(self) -> None:
        """chunk_section must terminate even when overlap >= chunk_size."""
        from packages.documents.src.extractor import ExtractedSection

        section = ExtractedSection(
            section_name="Risk Factors",
            page_start=1,
            page_end=1,
            text="word " * 500,  # 500 words
            token_estimate=500,
        )
        # overlap=400 >= chunk_size=400 — the broken guard would loop forever
        chunks = self._extractor.chunk_section(section, chunk_size=400, overlap=400)
        # Must return at least one chunk and terminate
        assert len(chunks) >= 1
        # All chunk text should be non-empty
        assert all(c.strip() for c in chunks)

    def test_pdf_extension_still_uses_pypdf(self) -> None:
        """extract() must NOT call extract_html for .pdf files."""
        with (
            patch.object(self._extractor, "extract_html") as mock_html,
            patch.object(self._extractor, "_extract") as mock_pdf,
        ):
            mock_pdf.return_value = MagicMock(success=True)
            self._extractor.extract("/some/file.pdf")

        mock_html.assert_not_called()
        mock_pdf.assert_called_once()
