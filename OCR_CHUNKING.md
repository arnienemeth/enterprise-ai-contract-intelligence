# OCR & Chunking — real-format contract ingestion

This document describes the ingestion layer added to the platform: **text
extraction ("OCR")** so the system accepts real contract files (PDF, DOCX,
scans) instead of only `.txt`, and **chunking** so long contracts are embedded
and retrieved section-by-section rather than as one blurry vector.

Together these close the top blocker from the production gap analysis: *"Now it
only processes `.txt`. Real contracts are PDF / DOCX / scans."*

---

## What changed

New package `ingestion/`:

- `ingestion/extractor.py` — `extract_text(file_bytes, filename) -> str`
- `ingestion/chunker.py` — `chunk_text(text, max_chars, overlap) -> list[str]`

Wired into the rest of the app:

- `POST /upload-contract` now runs `extract_text` on the raw uploaded bytes,
  so it accepts PDF / DOCX / TXT / MD (and scans when Document Intelligence is
  configured) instead of assuming UTF-8 text.
- `analyze_and_store()` / `add_document()` chunk the extracted text and store
  **one vector per chunk**; document-level stats dedupe by `doc_id`.
- `reindex.py` ingests every supported format from `documents/`, not just `.txt`.

---

## Text extraction (OCR) — dispatcher

Mirrors the existing Azure ↔ local vector-store pattern:

| Input | `AZURE_DOCINTEL_ENDPOINT` set | Not set (local only) |
|---|---|---|
| `.txt` / `.md` | local decode | local decode |
| **digital** PDF | local (`pdfplumber` → `pypdf`) | local |
| `.docx` | local (`python-docx`, incl. tables) | local |
| **scanned / image** PDF | **Azure AI Document Intelligence** (OCR) | clear error asking to enable it |
| images (`.png`, `.jpg`, …) | **Azure AI Document Intelligence** | unsupported error |

The local path handles *digital* PDFs/DOCX with no extra cloud resource. A
scanned PDF has no embedded text, so the extractor detects the empty result and
either OCRs it via Document Intelligence or returns an actionable error.

### Enabling Azure AI Document Intelligence

Provision an *Azure AI Document Intelligence* (Form Recognizer) resource, then
set in `.env` / Container App secrets:

```
AZURE_DOCINTEL_ENDPOINT=https://<resource>.cognitiveservices.azure.com/
AZURE_DOCINTEL_KEY=<key>
AZURE_DOCINTEL_MODEL=prebuilt-read      # OCR read model (default)
```

The SDK (`azure-ai-documentintelligence`) is imported lazily, so the app runs
fine with the feature off.

---

## Chunking

Long contracts exceed the embedding model's input limit
(`text-embedding-3-large` ≈ 8,191 tokens) and, embedded whole, produce one
averaged vector that retrieves poorly. `chunk_text` splits on natural
boundaries — blank lines, then `ARTICLE` / `SECTION` / `CLAUSE` / numbered
headings — and greedily packs them into windows of at most `max_chars`
(default **4,000**) with `overlap` (default **400**) characters of shared
context between neighbours so a clause spanning a boundary stays retrievable.

- A single oversized paragraph is hard-split on sentence boundaries as a last
  resort.
- Short documents return a single chunk; empty input returns `[]`.

### Storage / retrieval model

Each chunk is one row/vector carrying its parent's `doc_id` plus its own
`chunk_index`:

- **Semantic search / RAG** (`/ask`, `/semantic-search`) retrieve the most
  relevant *chunks* and cite the source file.
- **Dashboard / vendor analytics** dedupe by `doc_id`, so a 12-chunk contract
  still counts as **one** contract.

The Azure AI Search index gained `doc_id` (filterable) and `chunk_index`
(Int32) fields. `_ensure_index` detects a pre-chunking index and **recreates**
it with the correct schema — so after deploying, re-ingest:

```
python reindex.py --reset
```

---

## Dependencies added

```
pdfplumber                      # digital PDF text
pypdf                           # PDF fallback
python-docx                     # DOCX text + tables
azure-ai-documentintelligence   # OCR for scans/images (used when configured)
```

---

## Testing

`ingestion/` is dependency-free (no Azure, no OpenAI, no vector store), so it is
unit-testable in isolation: TXT/PDF/DOCX extraction, the scanned-PDF fallback
message, unsupported-type errors, and chunker coverage/overlap/boundary
behaviour all pass without any cloud calls.
