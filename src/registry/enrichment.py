"""Auto-enrichment for documents on registration.

Computes content_hash, file_format, file_size_bytes, and page_count
from staged files when accessible.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

CORPUS_DIR = os.environ.get("CORPUS_DIR", "")


def _find_file(filename: str, collections: list[str]) -> Path | None:
    """Locate a file in the corpus directory structure."""
    if not CORPUS_DIR:
        return None
    root = Path(CORPUS_DIR)
    if not root.is_dir():
        return None
    for coll in collections:
        candidate = root / coll / filename
        if candidate.is_file():
            return candidate
    candidate = root / filename
    if candidate.is_file():
        return candidate
    return None


def _compute_content_hash(filepath: Path) -> str:
    """SHA-256 of file content."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _detect_format(filename: str) -> str | None:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "pdf"
    if lower.endswith(".docx"):
        return "docx"
    if lower.endswith(".html") or lower.endswith(".htm"):
        return "html"
    if lower.endswith(".xlsx"):
        return "xlsx"
    if lower.endswith(".pptx"):
        return "pptx"
    return None


def _get_pdf_page_count(filepath: Path) -> int | None:
    """Attempt to get PDF page count without heavy dependencies."""
    try:
        content = filepath.read_bytes()
        count = content.count(b"/Type /Page") - content.count(b"/Type /Pages")
        return count if count > 0 else None
    except Exception:
        return None


def enrich_document(filename: str, collections: list[str]) -> dict:
    """Compute enrichment fields for a document file.

    Returns a dict with any of: content_hash, file_format, file_size_bytes, page_count.
    Only includes fields that could be computed.
    """
    result: dict = {}

    file_format = _detect_format(filename)
    if file_format:
        result["file_format"] = file_format

    filepath = _find_file(filename, collections)
    if filepath is None:
        logger.debug("Cannot enrich %s: file not found in corpus", filename)
        return result

    stat = filepath.stat()
    result["file_size_bytes"] = stat.st_size
    result["content_hash"] = _compute_content_hash(filepath)

    if file_format == "pdf":
        page_count = _get_pdf_page_count(filepath)
        if page_count:
            result["page_count"] = page_count

    return result
