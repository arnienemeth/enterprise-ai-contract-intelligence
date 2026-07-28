# Architecture

## Overview

The Enterprise AI Contract Intelligence Platform is a modular RAG system for contract analysis. Contracts are embedded into a vector store, analyzed by an LLM for risk, and made queryable through natural language. The current repository implements the **AI core** (FastAPI \+ Azure OpenAI \+ ChromaDB); the enterprise integration layer (SharePoint, Power Automate) is designed and documented but not yet coded.

---

## Target architecture (end state)

                        SharePoint

                  Contracts Repository

                          │

                          ▼

                  Power Automate Flow

                          │

                          ▼

                   FastAPI REST API                 \[implemented\]

                          │

         ┌────────────────┴────────────────┐

         ▼                                  ▼

   Azure OpenAI (chat)             Azure OpenAI (embeddings)   \[implemented\]

   risk / RAG answers              vectorization

         │                                  │

         └────────────────┬─────────────────┘

                          ▼

                  ChromaDB Vector Store            \[implemented\]

                          │

                          ▼

                   Semantic Search                 \[implemented\]

                          │

                          ▼

              Enterprise AI Answers / Risk JSON     \[implemented\]

                          │

                          ▼

               SharePoint Contract Register         \[designed\]

                          │

                          ▼

                    Risk Dashboard                  \[partial\]

---

## Implemented components

### 1\. FastAPI backend — `api/main.py`

The REST entry point. Loads Azure config from `.env`, constructs an `AzureOpenAI` client, and exposes the application endpoints. Two responsibilities dominate:

- **Contract ingestion \+ risk analysis** (`/upload-contract`)  
- **Knowledge retrieval** (`/ask`, `/semantic-search`, `/find-risky-contracts`)

### 2\. Embedding engine — `vector_store/embedding_engine.py`

Wraps ChromaDB and Azure embeddings. Three functions:

- `create_embedding(text)` — calls the Azure embedding deployment.  
- `add_document(text, filename, vendor, risk_level)` — embeds and stores with metadata.  
- `search_similar(query, top_k=3)` — embeds the query, runs a cosine-similarity search, and returns formatted results with a similarity score (`1 - distance`).

ChromaDB persists to `./vector_db` (`chroma.sqlite3`) under a collection named `enterprise_knowledge`.

### 3\. MCP server (prototype) — `mcp_server/server.py`

A minimal `FastMCP` server exposing `search_documents` and `invoice_lookup` tools over local files. **Not part of the production workflow** — reserved for future integration (e.g., exposing the platform's capabilities to an MCP-compatible client/agent).

---

## RAG data flow (`/ask`)

User question

      │

      ▼

create\_embedding(question)          \# Azure embeddings

      │

      ▼

ChromaDB cosine search (top-k)      \# nearest contracts

      │

      ▼

Build enterprise context           \# filename \+ vendor \+ risk \+ text

      │

      ▼

Chat Completion (gpt-4o-mini)       \# system \+ user prompt, temp 0.3

      │

      ▼

Answer \+ cited results (JSON)

## Ingestion flow (`/upload-contract`)

Upload file → decode UTF-8 → add\_document() → embed \+ store

                                   │

                                   ▼

                    Risk-analysis prompt → LLM (temp 0.2)

                                   │

                                   ▼

                    Strict JSON: risk\_score, risk\_level,

                    financial/compliance/liability/operational

                    risk, executive\_summary

---

## Designed (not yet implemented)

### SharePoint

Two objects, separating files from metadata:

- **Contracts Repository** — physical files (`contract.pdf`, `nda.pdf`, ...).  
- **Contract Register** — searchable metadata list: Title, Vendor, RiskScore, RiskLevel, ContractStatus, ExecutiveSummary, UploadDate, ReviewedBy, ReviewDate, FileLink.

### Power Automate

Planned flow:

File uploaded → Get file content → HTTP POST to FastAPI

             → receive AI JSON → update Contract Register → Teams notification

---

## Design principles

- **Modular / replaceable.** Each component (LLM, vector store, ingestion, UI) can be swapped without affecting the others. The local ChromaDB store is intentionally simple and is meant to be replaced by **Azure AI Search** in production.  
- **Structured LLM output.** Risk analysis returns strict JSON so downstream systems (SharePoint, dashboards) can consume it directly.  
- **Enterprise prompting.** Prompts target specific risk categories (financial, operational, compliance, GDPR, liability) rather than generic summarization.

