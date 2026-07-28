# Testing Guide

How to run and test the platform after the recent fixes. Commands are for Windows
(PowerShell / CMD). Run everything **from the project root**:
`C:\Projects\MCP\enterprise-ai-mcp-project`.

---

## Prerequisites

1. **Rotate your Azure OpenAI key** (the old one was exposed) and put the new value in `.env`.
   Your `.env` needs all five variables — see `.env.example`.
2. The AI endpoints (`/upload-contract`, `/ask`, `/semantic-search`, `/find-risky-contracts`,
   and `reindex.py`) call Azure and will fail without a valid key. The health and dashboard
   endpoints work without it.

---

## Step 1 — Set up the environment

```powershell
cd C:\Projects\MCP\enterprise-ai-mcp-project

# Activate the virtual environment (create it if it doesn't exist)
venv\Scripts\activate
# If you need to create it:  python -m venv venv   then activate

# Install/refresh dependencies
pip install -r requirements.txt
```

## Step 2 — Start the API

```powershell
uvicorn api.main:app --reload
```

You should see `Starting Enterprise AI API...` and Uvicorn running on
`http://127.0.0.1:8000`. Leave this window running.

> If you get `ModuleNotFoundError: vector_store`, you're not in the project root —
> `cd` into it and rerun.

## Step 3 — Open Swagger (interactive tester)

In a browser: **http://127.0.0.1:8000/docs**

This lists every endpoint with a **Try it out** button. It's the easiest way to test.

## Step 4 — Test the no-Azure endpoints first

These confirm the app is up without spending any Azure tokens.

| Endpoint | How | Expected |
|---|---|---|
| `GET /` | open http://127.0.0.1:8000/ | `{"message":"Enterprise AI API is running"}` |
| `POST /health-test` | Swagger → Execute | `{"status":"working"}` |
| `GET /dashboard` | open http://127.0.0.1:8000/dashboard | real counts + `by_vendor` (no longer zeros) |

At this point `/dashboard` will still show the **old** metadata (mostly `ACME` / `High`)
because those embeddings were created by the old code. Step 5 fixes that.

## Step 4b — Visual dashboard (no Azure)

For a human-friendly view instead of raw JSON, open:

**http://127.0.0.1:8000/dashboard-view**

This is an HTML page (endpoint `GET /dashboard-view`) that shows KPI cards, a risk
doughnut chart, and a vendor table. It fetches the same data as `GET /dashboard`, so it
updates whenever you reload after adding contracts. Use the **Refresh** button to re-pull.

> Reminder: `/dashboard` returns JSON (for machines / Power Automate); `/dashboard-view`
> returns the pretty page (for people).

**Vendor analytics:** `GET http://127.0.0.1:8000/vendor-analytics` returns JSON ranking each
vendor by a weighted risk score (High=3, Medium=2, Low=1) with a per-vendor breakdown and the
top-3 riskiest vendors. The dashboard's "Vendors by risk" table is powered by this endpoint.

## Step 5 — Reindex with correct metadata (needs Azure)

In a **second** terminal (venv activated, in the project root):

```powershell
python reindex.py --reset
```

This wipes the vector store and re-embeds every file in `documents/`, storing the **real**
vendor and risk level the AI extracts. You'll see one line per document, e.g.:

```
indexed: high_risk_contract.txt          vendor=SmartVision AI      risk=High
```

Now refresh **http://127.0.0.1:8000/dashboard** — the counts and `by_vendor` breakdown
should reflect the true risk distribution.

## Step 6 — Test the AI endpoints (needs Azure)

**`POST /upload-contract`** — in Swagger, click *Try it out*, choose a file from
`documents/` (e.g. `sample_contract.txt`), and Execute. Expect JSON like:

```json
{
  "vendor": "SmartVision AI",
  "risk_score": 85,
  "risk_level": "High",
  "financial_risk": "...",
  "compliance_risk": "...",
  "liability_risk": "...",
  "operational_risk": "...",
  "executive_summary": "...",
  "filename": "sample_contract.txt"
}
```

**`POST /ask`** — request body:

```json
{ "question": "Which contracts have the worst payment terms?" }
```

Expect an `answer`, plus `semantic_results` (the contracts it used) and `results_count`.

**`POST /semantic-search`** — same body shape; returns the most similar contracts with scores.

**`POST /find-risky-contracts`** — same body shape; returns contracts matching risk keywords.

### Same tests via curl (optional)

```powershell
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/dashboard
curl -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" -d "{\"question\":\"Which vendors have GDPR issues?\"}"
```

---

## Troubleshooting

- **`{"error":"Collection [id] does not exist."}`** → this happened with an older version of
  `reset_collection()` that deleted and recreated the collection while the server held a handle
  to the old one. It's now fixed: `reset_collection()` clears documents *in place* and keeps the
  same collection id. If you still see it (e.g. after an old run), just **restart the server**
  (Ctrl+C, then `uvicorn api.main:app --reload`) and it will bind to the current collection.
- **500 error on an AI endpoint** → almost always the Azure config: wrong key, endpoint,
  API version, or deployment name in `.env`. Check the Uvicorn console for the traceback.
- **`ModuleNotFoundError: vector_store`** → run from the project root.
- **ChromaDB `disk I/O error`** → only happens on network/cloud-synced drives; use a local disk.
- **`/dashboard` shows old ACME/High values** → run `python reindex.py --reset` (Step 5).
