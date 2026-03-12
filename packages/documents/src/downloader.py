"""Document downloader with safety guards.

Downloads PDFs from SGX RegNet and company IR pages.
Guards: max 50MB, only PDF/HTML content types, timeout 60s.
Stores to local filesystem under DOCUMENT_STORE_PATH env var (default: ./document_store).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import httpx


@dataclass
class DownloadResult:
    """Result of a document download attempt."""

    success: bool
    file_path: str | None  # absolute path if downloaded
    file_size_bytes: int
    content_type: str
    error: str | None


class DocumentDownloader:
    """Downloads documents from remote URLs with safety guards.

    Guards enforced:
    - Maximum file size: 50 MB (checked via Content-Length and during streaming)
    - Allowed content types: application/pdf, text/html
    - Network timeout: 60 seconds
    - Directory structure: {store_path}/{company_id}/{doc_type}/{filename}

    Never raises — all errors are captured in DownloadResult.error.
    """

    MAX_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB hard limit
    ALLOWED_CONTENT_TYPES = ["application/pdf", "text/html"]

    def __init__(self, store_path: str | None = None) -> None:
        self._store_path = store_path or os.getenv("DOCUMENT_STORE_PATH", "./document_store")

    async def download(
        self,
        url: str,
        company_id: str,
        doc_type: str,
        filename: str | None = None,
    ) -> DownloadResult:
        """Download a document from a URL and store it locally.

        Args:
            url: Remote URL to download from.
            company_id: Company identifier — used in directory path.
            doc_type: Document category (e.g. "annual_report", "sustainability") — used in path.
            filename: Optional explicit filename. If omitted, derived from URL basename.

        Returns:
            DownloadResult with success=True and file_path on success,
            or success=False and error on any failure.
        """
        try:
            return await self._download(url, company_id, doc_type, filename)
        except Exception as exc:
            return DownloadResult(
                success=False,
                file_path=None,
                file_size_bytes=0,
                content_type="",
                error=f"Unexpected error: {exc}",
            )

    async def _download(
        self,
        url: str,
        company_id: str,
        doc_type: str,
        filename: str | None,
    ) -> DownloadResult:
        """Inner download implementation — may raise; caller wraps in try/except."""
        timeout = httpx.Timeout(60.0, connect=10.0)

        # Stream the response so we can enforce size limits incrementally.
        # The two context managers are combined in a single async with statement
        # to satisfy SIM117 (flake8-simplify).
        async with (
            httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client,
            client.stream("GET", url) as response,
        ):
            response.raise_for_status()

            # --- Content-Type guard ---
            raw_content_type = response.headers.get("content-type", "")
            content_type = raw_content_type.split(";")[0].strip().lower()

            if not any(allowed in content_type for allowed in self.ALLOWED_CONTENT_TYPES):
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size_bytes=0,
                    content_type=content_type,
                    error=(
                        f"Rejected content type '{content_type}'. "
                        f"Allowed: {self.ALLOWED_CONTENT_TYPES}"
                    ),
                )

            # --- Content-Length guard (pre-flight) ---
            content_length_header = response.headers.get("content-length", "")
            if content_length_header:
                try:
                    declared_size = int(content_length_header)
                    if declared_size > self.MAX_SIZE_BYTES:
                        return DownloadResult(
                            success=False,
                            file_path=None,
                            file_size_bytes=declared_size,
                            content_type=content_type,
                            error=(
                                f"File too large: {declared_size:,} bytes "
                                f"(limit {self.MAX_SIZE_BYTES:,} bytes)"
                            ),
                        )
                except ValueError:
                    pass  # Malformed Content-Length — proceed and check during streaming

            # --- Stream in chunks, enforce size limit ---
            chunks: list[bytes] = []
            total_bytes = 0

            async for chunk in response.aiter_bytes(chunk_size=65536):
                total_bytes += len(chunk)
                if total_bytes > self.MAX_SIZE_BYTES:
                    return DownloadResult(
                        success=False,
                        file_path=None,
                        file_size_bytes=total_bytes,
                        content_type=content_type,
                        error=(
                            f"Download aborted: streamed size exceeded "
                            f"{self.MAX_SIZE_BYTES:,} bytes limit"
                        ),
                    )
                chunks.append(chunk)

            data = b"".join(chunks)

        # --- Resolve destination path ---
        resolved_filename = filename or self._filename_from_url(url, content_type)
        dest = (
            Path(self._store_path)
            / _sanitise_path_component(company_id)
            / _sanitise_path_component(doc_type)
            / resolved_filename
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

        return DownloadResult(
            success=True,
            file_path=str(dest.resolve()),
            file_size_bytes=len(data),
            content_type=content_type,
            error=None,
        )

    def get_store_path(self) -> str:
        """Return the root document store path."""
        return self._store_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _filename_from_url(self, url: str, content_type: str) -> str:
        """Derive a safe filename from the URL basename."""
        parsed = urlparse(url)
        basename = Path(parsed.path).name or "document"
        # Strip query strings that may have leaked into the name
        basename = basename.split("?")[0].split("#")[0]
        # Keep only safe characters
        basename = re.sub(r"[^\w.\-]", "_", basename)
        basename = basename.strip("._") or "document"
        # Ensure .pdf extension for PDFs
        if "pdf" in content_type and not basename.lower().endswith(".pdf"):
            basename += ".pdf"
        return basename


def _sanitise_path_component(value: str) -> str:
    """Replace unsafe filesystem characters in a path component."""
    return re.sub(r"[^\w.\-]", "_", value)


@lru_cache
def get_document_downloader() -> DocumentDownloader:
    """Return a cached singleton DocumentDownloader instance."""
    return DocumentDownloader()
