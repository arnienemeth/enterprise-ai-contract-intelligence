# Project Status

**Last updated:** 2026-07-20
**Version:** MVP v1.0

This document tracks what is **verified working in the code**, what is **designed but not
implemented**, and the **known issues**. It is deliberately conservative: an item is only
"Done" if it exists and runs in this repository.

---

## Legend

- ✅ **Done** — implemented and verified in code
- 🟡 **Partial** — present but incomplete or buggy
- 📐 **Designed** — architecture defined, no code in repo yet
- ⬜ **Planned** — future work

---

## Component status

| Area | Item | Status | Notes |
|------|------|:------:|-------|
| Backend | FastAPI app (`api/main.py`) | ✅ | Boots; 7 app endpoints + Swagger |
| Backend | `requirements.txt` | ✅ | Added (was missing); versions verified |
| AI | Azure OpenAI chat client | ✅ | `gpt-4o-mini` deployment |
| AI | Azure OpenAI embeddings | ✅ | `embedding-test` deployment |
| AI | Structured risk-analysis prompt | ✅ | Returns strict JSON |
| AI | RAG answer prompt | ✅ | Search → context → LLM |
| Vector | ChromaDB persistent store | ✅ | `./vector_db`, cosine similarity |
| Vector | Semantic search | ✅ | `search_similar()` top-k |
| Endpoint | `GET /` | ✅ | Health |
| Endpoint | `POST /health-test` | ✅ | Status |
| Endpoint | `POST /upload-contract` | ✅ | Fixed: extracts vendor via AI, stores real vendor/risk metadata |
| Endpoint | `POST /ask` | ✅ | RAG |
| Endpoint | `POST /semantic-search` | ✅ | Returns raw results |
| Endpoint | `POST /find-risky-contracts` | ✅ | Keyword filter over search results |
| Endpoint | `GET /dashboard` | ✅ | Fixed: queries ChromaDB for real counts (by level + by vendor) |
| Endpoint | `GET /dashboard-view` | ✅ | New: HTML dashboard (cards, risk chart, vendor table) |
| Endpoint | `GET /vendor-analytics` | ✅ | New: vendors ranked by weighted risk (high=3/med=2/low=1) |
| Endpoint | `POST /analyze-contract` | ✅ | New: JSON-in analysis for Power Automate |
| Security | API key auth (`X-API-Key`) | ✅ | Protects the AI/token-spending endpoints; dashboard stays public |
| Repo hygiene | `.gitignore` / `.env.example` | ✅ | Added |
| MCP | `mcp_server/server.py` | 🟡 | Prototype only; not in production workflow |
| Deploy | Azure Container Apps (live URL) | ✅ | Deployed; public HTTPS endpoint |
| Deploy | CI/CD (GitHub Actions) | ✅ | Auto build + deploy on push to `main` |
| Integration | Power Automate ↔ FastAPI | ✅ | `/analyze-contract` ready; flow guide in POWER_AUTOMATE_SETUP.md |
| Integration | SharePoint Repository + Register | 🟡 | Design + step-by-step guide provided; user configures in M365 |
| Ops | OCR (Azure AI Document Intelligence) | ⬜ | Not started |
| Ops | Azure AI Search (prod vector DB) | ⬜ | Not started |

---

## Completion estimate

| Layer | Estimate |
|-------|:--------:|
| Core AI pipeline (ingest → embed → analyze → RAG) | ~90% |
| MVP end-to-end (incl. SharePoint / Power Automate loop) | ~60% |
| Production-ready enterprise solution | ~40–45% |

---

## Resolved issues

1. **`/dashboard` always returned zeros — FIXED.** It read a non-existent
   `vector_store/vector_db.json`. It now calls `get_collection_stats()` and aggregates
   real counts from the ChromaDB collection (by risk level and by vendor). Verified: returns
   the true document count instead of zeros.
2. **`/upload-contract` stored hardcoded metadata — FIXED.** Previously `vendor="ACME"` and
   `risk_level="High"` were hardcoded. The endpoint now runs the AI analysis first (the prompt
   also extracts the vendor), then stores the real `vendor` and `risk_level`. JSON parsing also
   tolerates accidental ```` ```json ```` code fences.
3. **No `requirements.txt` originally — FIXED.** Added and pinned to verified versions.

## Open issues

4. **Secret hygiene.** A live API key was present in `.env`. Rotate it and rely on `.env.example`.
   (This is the main item left before making the repo public.)

### Resolved (repo cleanup)

- Removed all legacy artifacts: `faiss.index`, `documents.pkl`, every `- Copy` duplicate,
  the double-extension `*.txt.txt` files, and browser-download duplicates.
- Re-ingested contracts via the fixed `/upload-contract` / `reindex.py`, so vendor and
  risk metadata are accurate (no more hardcoded `ACME` / `High`).
- Rewrote `README.md` with correct links and fenced code blocks.

---

## Environment notes

- The app must be run **from the project root** (ChromaDB path is relative: `./vector_db`).
- ChromaDB's SQLite backend does not run reliably on some network/FUSE-mounted filesystems
  ("disk I/O error"). Use a local disk. This is an environment limitation, not a code defect.
