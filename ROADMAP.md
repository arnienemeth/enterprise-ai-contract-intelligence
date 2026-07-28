# Roadmap

The near-term priority is to finish the **existing end-to-end scenario** rather than adding new surface area. A fully working ingest → analyze → store → query → dashboard loop is more valuable for a portfolio / interview demo than a wider but half-finished feature set.

---

## Phase 0 — Stabilize (immediate)

- [x] Add `requirements.txt`, `.env.example`, `.gitignore`  
- [ ] Rotate the exposed Azure OpenAI key  
- [ ] Fix `/dashboard` to query ChromaDB (currently returns zeros)  
- [ ] Fix `/upload-contract` to store the AI's real vendor/risk metadata (not hardcoded)  
- [ ] Remove legacy artifacts (FAISS files, `- Copy` duplicates, double `.txt.txt`)

## Phase 1 — Complete the MVP loop

- [ ] Power Automate → HTTP → FastAPI integration  
- [ ] Automatic write-back of AI results to the SharePoint Contract Register  
- [ ] Working dashboard endpoint backed by real data  
- [ ] Vendor analytics (top-risk vendors, highest liability, most GDPR issues)  
- [ ] Multi-contract questions ("which vendors have payment risk?", "above-average liability")

## Phase 2 — Production hardening

- [ ] Authentication & authorization (Azure Entra ID)  
- [ ] Replace local ChromaDB with **Azure AI Search**  
- [ ] OCR via **Azure AI Document Intelligence** (PDF / Word / scanned docs)  
- [ ] Logging, monitoring, error handling  
- [ ] CI/CD pipeline  
- [ ] Azure deployment (App Service / Functions / Container Apps)  
- [ ] Power BI live dashboard

## Phase 3 — Advanced intelligence

- [ ] Contract expiration alerts & renewal reminders  
- [ ] Clause extraction and clause-level comparison  
- [ ] Contract versioning  
- [ ] Approval workflows  
- [ ] AI recommendations

## Phase 4 — Multi-agent platform

- [ ] Contract Agent, Legal Agent, Compliance Agent, Finance Agent, Procurement Agent  
- [ ] Manager Copilot (natural-language governance assistant)  
- [ ] Copilot Studio integration

---

## Guiding notes

- Keep the architecture **modular** — each component replaceable without breaking others.  
- Do **not** replace the local vector search until Azure AI Search is introduced; the simple store exists to demonstrate the RAG architecture clearly.  
- Prioritize a **demonstrable end-to-end flow** over breadth of features.

