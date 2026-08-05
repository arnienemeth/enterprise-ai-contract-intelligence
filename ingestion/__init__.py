"""Ingestion layer: turn a raw uploaded file into clean, chunked text.

Two responsibilities, kept separate so each is testable on its own:

  * extractor.py  — bytes -> plain text  (OCR / document parsing)
  * chunker.py    — long text -> overlapping chunks (for embedding + retrieval)

Both are backend-agnostic and have no dependency on the vector store or the
web layer, so they can be unit-tested without Azure or a running server.
"""

from ingestion.extractor import extract_text, ExtractionError, SUPPORTED_EXTENSIONS
from ingestion.chunker import chunk_text

__all__ = [
    "extract_text",
    "ExtractionError",
    "SUPPORTED_EXTENSIONS",
    "chunk_text",
]
