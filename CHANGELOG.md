# Changelog

All notable changes to this project are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

---

## \[Unreleased\]

### Added

- `requirements.txt` with verified, pinned runtime dependencies (was previously missing).  
- `.env.example` template (variable names only, no secrets).  
- `.gitignore` excluding `.env`, `venv/`, vector store, and legacy `- Copy` files.  
- Professional documentation set: `README.md`, `PROJECT_STATUS.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `CHANGELOG.md`, and a full technical document (`.docx` / `.pdf`).  
- `get_collection_stats()` in `embedding_engine.py` — aggregates real counts (by risk level and by vendor) from ChromaDB.

### Fixed

- **`/dashboard`** now queries ChromaDB via `get_collection_stats()` instead of reading a
  non-existent `vector_store/vector_db.json`. Returns true counts (verified: 8 documents) plus
  a per-vendor breakdown, instead of always returning zeros.  
- **`/upload-contract`** now runs the AI risk analysis first (the prompt also extracts the
  vendor) and stores the real `vendor` and `risk_level` in the vector store, instead of the
  hardcoded `ACME` / `High`. JSON parsing tolerates accidental ```` ```json ```` code fences,
  and the contract is still stored (with `Unknown` metadata) if the AI returns invalid JSON.

### Notes

- Documentation was reconciled against the **actual source code**. The prior README described an aspirational structure (e.g., a FAISS/JSON vector store, a `requirements.txt` in root) that did not match the repository. Docs now reflect reality: ChromaDB is the active vector store, and verified-vs-planned status is tracked explicitly in `PROJECT_STATUS.md`.  
- The 8 documents already in the store were ingested by the old code and still carry
  `vendor=ACME` / `risk_level=High`; re-ingest via the fixed endpoint for accurate metadata.

### Known issues carried forward

- Legacy FAISS artifacts and `- Copy` duplicates remain in the tree.  
- A live API key was present in `.env` — rotate it.

---

## \[MVP v1.0\] — 2025 (baseline, migrated from prior development)

### Added

- FastAPI backend (`api/main.py`) with `/`, `/ask`, `/upload-contract`, `/semantic-search`, `/find-risky-contracts`, `/dashboard`, `/health-test`.  
- Azure OpenAI integration for chat completions and embeddings.  
- ChromaDB persistent vector store with cosine-similarity semantic search.  
- RAG pipeline (semantic search → enterprise context → LLM answer).  
- Structured contract risk analysis returning strict JSON.  
- Prototype MCP server (`mcp_server/server.py`) — not in production workflow.  
- Sample contract documents for testing.

