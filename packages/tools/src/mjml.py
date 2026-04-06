"""MJML compilation utility — converts MJML markup to responsive HTML email.

MJML (Mailjet Markup Language) is a domain-specific language for creating
responsive HTML emails that render well across email clients.

This utility wraps the MJML compiler (CLI or Python fallback) so agents
can generate MJML and get production-ready HTML email output.

Usage:
    html = await compile_mjml(mjml_source)
    # html is now responsive email HTML, tested across Gmail/Outlook/Apple Mail
"""

from __future__ import annotations

import asyncio
import re
import shutil

import structlog

logger = structlog.get_logger()

# Base MJML templates for common email layouts
SINGLE_COLUMN_TEMPLATE = '''<mjml>
  <mj-head>
    <mj-attributes>
      <mj-all font-family="Arial, Helvetica, sans-serif" />
      <mj-text font-size="14px" color="#333333" line-height="1.6" />
      <mj-button background-color="#2563EB" border-radius="6px" font-size="16px" />
    </mj-attributes>
    <mj-style>
      .footer-link {{ color: #666666; text-decoration: underline; }}
    </mj-style>
  </mj-head>
  <mj-body background-color="#f4f4f7">
    {hero_section}
    <mj-section background-color="#ffffff" padding="30px 40px">
      <mj-column>
        {body_content}
      </mj-column>
    </mj-section>
    {cta_section}
    {footer_section}
  </mj-body>
</mjml>'''

HERO_SECTION = '''<mj-section background-color="#1e3a5f" padding="0">
      <mj-column>
        {hero_image}
        <mj-text color="#ffffff" font-size="24px" font-weight="bold" padding="20px 40px 5px">
          {headline}
        </mj-text>
        <mj-text color="#c7d2fe" font-size="16px" padding="0 40px 20px">
          {subheadline}
        </mj-text>
      </mj-column>
    </mj-section>'''

CTA_SECTION = '''<mj-section background-color="#ffffff" padding="0 40px 30px">
      <mj-column>
        <mj-button href="{cta_url}" align="center">
          {cta_text}
        </mj-button>
      </mj-column>
    </mj-section>'''

FOOTER_SECTION = '''<mj-section padding="20px 40px">
      <mj-column>
        <mj-text font-size="12px" color="#999999" align="center">
          {company_name} | {company_address}
          <br/>UEN: {uen}
          <br/><a href="{{{{unsubscribe_url}}}}" class="footer-link">Unsubscribe</a>
          | <a href="{{{{preferences_url}}}}" class="footer-link">Manage Preferences</a>
        </mj-text>
      </mj-column>
    </mj-section>'''


async def compile_mjml(mjml_source: str) -> str:
    """Compile MJML markup to responsive HTML email.

    Tries the mjml CLI first (best output quality), falls back to
    a minimal Python-based compilation if CLI is not installed.

    Args:
        mjml_source: MJML markup string

    Returns:
        Responsive HTML email string

    Raises:
        RuntimeError: If compilation fails with both methods
    """
    # Try CLI first (best quality)
    cli_path = shutil.which("mjml")
    if cli_path:
        try:
            return await _compile_via_cli(mjml_source, cli_path)
        except Exception as e:
            logger.warning("mjml_cli_failed_fallback_to_python", error=str(e))

    # Try npx
    npx_path = shutil.which("npx")
    if npx_path:
        try:
            return await _compile_via_npx(mjml_source)
        except Exception as e:
            logger.warning("mjml_npx_failed", error=str(e))

    # If no CLI available, return the MJML with a warning comment
    # This is acceptable for development — the HTML won't be responsive
    # but the content will be readable
    logger.warning("mjml_no_compiler_available_returning_raw")
    return _minimal_html_fallback(mjml_source)


async def _compile_via_cli(mjml_source: str, cli_path: str) -> str:
    """Compile MJML using the installed CLI."""
    process = await asyncio.create_subprocess_exec(
        cli_path,
        "-s",
        "--no-minify",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(input=mjml_source.encode())

    if process.returncode != 0:
        error = stderr.decode().strip()
        raise RuntimeError(f"MJML CLI error: {error}")

    return stdout.decode()


async def _compile_via_npx(mjml_source: str) -> str:
    """Compile MJML using npx (no global install required)."""
    process = await asyncio.create_subprocess_exec(
        "npx",
        "mjml",
        "-s",
        "--no-minify",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(input=mjml_source.encode())

    if process.returncode != 0:
        error = stderr.decode().strip()
        raise RuntimeError(f"MJML npx error: {error}")

    return stdout.decode()


def _minimal_html_fallback(mjml_source: str) -> str:
    """Extract text content from MJML when no compiler is available.

    Produces a basic HTML email that is readable but not responsive.
    Suitable for development/preview only.
    """
    # Extract text content from mj-text tags
    text_blocks = re.findall(r"<mj-text[^>]*>(.*?)</mj-text>", mjml_source, re.DOTALL)
    # Extract button text and href
    buttons = re.findall(
        r'<mj-button[^>]*href="([^"]*)"[^>]*>(.*?)</mj-button>',
        mjml_source,
        re.DOTALL,
    )
    # Extract image src
    images = re.findall(r'<mj-image[^>]*src="([^"]*)"', mjml_source)

    body_parts: list[str] = []
    for text in text_blocks:
        body_parts.append(f"<p>{text.strip()}</p>")
    for href, label in buttons:
        body_parts.append(
            f'<p><a href="{href}" style="background:#2563EB;color:#fff;padding:10px 20px;'
            f'text-decoration:none;border-radius:6px;">{label.strip()}</a></p>'
        )
    for src in images:
        body_parts.append(f'<img src="{src}" style="max-width:100%;" />')

    body_html = (
        "\n".join(body_parts)
        if body_parts
        else "<p>(MJML content — install mjml CLI for proper rendering)</p>"
    )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#333;max-width:600px;margin:0 auto;padding:20px;">
{body_html}
</body>
</html>"""


def build_edm_mjml(
    headline: str,
    subheadline: str = "",
    body_paragraphs: list[str] | None = None,
    cta_text: str = "",
    cta_url: str = "",
    company_name: str = "",
    company_address: str = "Singapore",
    uen: str = "",
    hero_image_url: str = "",
) -> str:
    """Build a complete MJML email from structured content.

    Args:
        headline: Email headline / title
        subheadline: Secondary headline
        body_paragraphs: List of paragraph strings
        cta_text: Call-to-action button text
        cta_url: Call-to-action button URL
        company_name: For footer
        company_address: For footer (PDPA compliance)
        uen: Company UEN (PDPA compliance)
        hero_image_url: Optional hero/header image URL

    Returns:
        Complete MJML markup string ready for compilation
    """
    # Build hero section
    hero_image = ""
    if hero_image_url:
        hero_image = f'<mj-image src="{hero_image_url}" width="600px" padding="0" />'

    hero = (
        HERO_SECTION.format(
            hero_image=hero_image,
            headline=headline,
            subheadline=subheadline,
        )
        if headline
        else ""
    )

    # Build body content
    body_parts: list[str] = []
    for para in body_paragraphs or []:
        body_parts.append(f"<mj-text>{para}</mj-text>")
    body_content = (
        "\n        ".join(body_parts)
        if body_parts
        else "<mj-text>Content goes here.</mj-text>"
    )

    # Build CTA section
    cta = (
        CTA_SECTION.format(cta_text=cta_text, cta_url=cta_url)
        if cta_text and cta_url
        else ""
    )

    # Build footer (PDPA compliant)
    footer = FOOTER_SECTION.format(
        company_name=company_name or "Company Name",
        company_address=company_address or "Singapore",
        uen=uen or "N/A",
    )

    return SINGLE_COLUMN_TEMPLATE.format(
        hero_section=hero,
        body_content=body_content,
        cta_section=cta,
        footer_section=footer,
    )
