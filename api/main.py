from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from openai import AzureOpenAI
from dotenv import load_dotenv

from vector_store.embedding_engine import (
    add_document,
    search_similar,
    get_collection_stats,
    get_all_metadata
)

import os
import json

# ==========================================
# LOAD ENVIRONMENT
# ==========================================

load_dotenv()

print("Starting Enterprise AI API...")

# ==========================================
# FASTAPI APP
# ==========================================

app = FastAPI(
    title="Enterprise AI API",
    description="AI-powered enterprise contract intelligence system",
    version="1.0"
)

# ==========================================
# AZURE OPENAI CLIENT
# ==========================================

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

# ==========================================
# MODELS
# ==========================================

class Question(BaseModel):
    question: str

# ==========================================
# ROOT
# ==========================================

@app.get("/")
def root():

    return {
        "message": "Enterprise AI API is running"
    }

# ==========================================
# ASK AI
# ==========================================

@app.post("/ask")
def ask_ai(data: Question):

    print(f"Question received: {data.question}")

    # VECTOR SEARCH
    semantic_results = search_similar(data.question)

    semantic_context = ""

    clean_results = []

    for result in semantic_results:

        # SAFE EXTRACTION
        if isinstance(result, dict):

            text = str(result.get("text", ""))
            filename = str(result.get("filename", "unknown"))
            vendor = str(result.get("vendor", "unknown"))
            risk_level = str(result.get("risk_level", "unknown"))
            score = str(result.get("score", ""))

            # ENTERPRISE CONTEXT
            semantic_context += f"""
FILE: {filename}
VENDOR: {vendor}
RISK LEVEL: {risk_level}
SIMILARITY SCORE: {score}

CONTENT:
{text}

----------------------------------------
"""

            # CLEAN RESPONSE
            clean_results.append({
                "filename": filename,
                "vendor": vendor,
                "risk_level": risk_level,
                "score": score,
                "text": text
            })

        # FALLBACK STRING SUPPORT
        elif isinstance(result, str):

            semantic_context += result + "\n\n"

            clean_results.append({
                "text": result
            })

        # UNKNOWN OBJECT SUPPORT
        else:

            text = str(result)

            semantic_context += text + "\n\n"

            clean_results.append({
                "text": text
            })

    # EMPTY RESULTS
    if semantic_context.strip() == "":

        semantic_context = "No relevant enterprise knowledge found."

    # FINAL ENTERPRISE CONTEXT
    enterprise_context = semantic_context

    # PROMPT
    prompt = f"""
User Question:
{data.question}

Relevant Enterprise Knowledge:
{enterprise_context}

Instructions:
- Answer professionally
- Use enterprise knowledge
- Mention filenames if relevant
- Identify risks if relevant
- Mention GDPR/compliance/liability concerns if found
- Be concise but useful
"""

    # OPENAI CALL
    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {
                "role": "system",
                "content": """
You are an enterprise AI assistant specializing in:
- contracts
- GDPR
- compliance
- liability
- enterprise governance
- financial risk
- procurement risk
- vendor risk analysis
"""
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3
    )

    answer = response.choices[0].message.content

    # RETURN RESPONSE
    return {
        "question": data.question,
        "answer": answer,
        "semantic_results": clean_results,
        "results_count": len(clean_results)
    }

# ==========================================
# UPLOAD CONTRACT
# ==========================================

@app.post("/upload-contract")
async def upload_contract(file: UploadFile = File(...)):

    print(f"Uploading file: {file.filename}")

    # READ FILE
    content = await file.read()

    contract = content.decode("utf-8")

    # ANALYSIS PROMPT
    # NOTE: the contract is stored AFTER analysis (below) so we can save the
    # real vendor / risk_level returned by the AI instead of hardcoded values.
    prompt = f"""
Analyze this enterprise contract.

Identify:
- vendor / counterparty name (extract from the contract text)
- overall risk score (0-100)
- risk level (Low / Medium / High)
- financial risks
- compliance concerns
- GDPR risks
- liability risks
- operational risks
- suspicious clauses

Contract:
{contract}

Return ONLY valid JSON in this exact format:

{{
    "vendor": "vendor name or Unknown",
    "risk_score": 75,
    "risk_level": "High",
    "financial_risk": "description",
    "compliance_risk": "description",
    "liability_risk": "description",
    "operational_risk": "description",
    "executive_summary": "short executive summary"
}}
"""

    # AI CALL
    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {
                "role": "system",
                "content": """
You are a senior enterprise contract risk analyst.

IMPORTANT:
Return ONLY valid JSON.
No markdown.
No explanations.
"""
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2
    )

    ai_response = response.choices[0].message.content

    print("Contract upload analysis completed.")

    # Parse the AI JSON (tolerate accidental ```json code fences)
    cleaned = ai_response.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.lstrip("`")
        if cleaned[:4].lower() == "json":
            cleaned = cleaned[4:]
        cleaned = cleaned.strip().rstrip("`").strip()

    try:

        parsed_json = json.loads(cleaned)

    except Exception as e:

        # Still store the contract so it stays searchable, with Unknown metadata
        add_document(
            text=contract,
            filename=file.filename,
            vendor="Unknown",
            risk_level="Unknown"
        )

        return {
            "error": "Invalid JSON returned by AI",
            "raw_response": ai_response,
            "exception": str(e)
        }

    # Store the contract with the REAL vendor / risk metadata from the AI
    vendor = str(parsed_json.get("vendor", "Unknown")).strip() or "Unknown"
    risk_level = str(parsed_json.get("risk_level", "Unknown")).strip() or "Unknown"

    add_document(
        text=contract,
        filename=file.filename,
        vendor=vendor,
        risk_level=risk_level
    )

    parsed_json["filename"] = file.filename

    return parsed_json

# ==========================================
# SEMANTIC SEARCH
# ==========================================

@app.post("/semantic-search")
def semantic_search(data: Question):

    results = search_similar(data.question)

    return {
        "results": results
    }

# ==========================================
# FIND RISKY CONTRACTS
# ==========================================

@app.post("/find-risky-contracts")
def find_risky_contracts(data: Question):

    results = search_similar(data.question)

    risky = []

    for result in results:

        # HANDLE DICTIONARY
        if isinstance(result, dict):

            text = result.get("text", "").lower()

        else:

            text = str(result).lower()

        if (
            "risk" in text or
            "penalty" in text or
            "termination" in text or
            "compliance" in text or
            "gdpr" in text or
            "liability" in text or
            "lawsuit" in text or
            "breach" in text
        ):

            risky.append(result)

    return {
        "matching_risky_contracts": risky,
        "count": len(risky)
    }

# ==========================================
# DASHBOARD
# ==========================================

@app.get("/dashboard")
def dashboard():

    try:

        # Read real counts from the ChromaDB vector store
        total, counts, vendors = get_collection_stats()

        return {
            "total_contracts": total,
            "high_risk": counts["high"],
            "medium_risk": counts["medium"],
            "low_risk": counts["low"],
            "unknown_risk": counts["unknown"],
            "by_vendor": vendors
        }

    except Exception as e:

        return {
            "error": str(e)
        }


# ==========================================
# VENDOR ANALYTICS
# ==========================================
#
# Turns the per-contract metadata into vendor-level intelligence: for each
# vendor, how many contracts they have and how those break down by risk level.
#
# To rank "who is the riskiest vendor" we compute a simple weighted score:
#     risk_weight = (# High x 3) + (# Medium x 2) + (# Low x 1)
# High-risk contracts count most, so a vendor with several high-risk agreements
# rises to the top. avg_risk = risk_weight / total gives an at-a-glance severity
# per contract (closer to 3 = mostly high risk, closer to 1 = mostly low).

# Numeric weight per risk level (unknown contributes nothing to the score).
RISK_WEIGHTS = {"high": 3, "medium": 2, "low": 1, "unknown": 0}


@app.get("/vendor-analytics")
def vendor_analytics():

    try:

        metadatas = get_all_metadata()

        # Group contracts by vendor, tallying each risk level.
        vendors = {}

        for meta in metadatas:

            meta = meta or {}

            vendor = str(meta.get("vendor", "Unknown")).strip() or "Unknown"
            level = str(meta.get("risk_level", "")).strip().lower()

            if level not in RISK_WEIGHTS:
                level = "unknown"

            # Create the vendor's record the first time we see it.
            record = vendors.setdefault(vendor, {
                "vendor": vendor,
                "total": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "unknown": 0,
            })

            record["total"] += 1
            record[level] += 1

        # Compute the weighted risk score for each vendor.
        result = []

        for record in vendors.values():

            weight = (
                record["high"] * RISK_WEIGHTS["high"]
                + record["medium"] * RISK_WEIGHTS["medium"]
                + record["low"] * RISK_WEIGHTS["low"]
            )

            record["risk_weight"] = weight
            record["avg_risk"] = round(weight / record["total"], 2) if record["total"] else 0

            result.append(record)

        # Rank: highest risk weight first, then by number of high-risk contracts.
        result.sort(key=lambda r: (r["risk_weight"], r["high"], r["total"]), reverse=True)

        return {
            "vendor_count": len(result),
            "top_risk_vendors": [r["vendor"] for r in result[:3]],
            "vendors": result,
        }

    except Exception as e:

        return {"error": str(e)}


# ==========================================
# DASHBOARD (VISUAL / HTML)
# ==========================================
#
# The /dashboard endpoint above returns raw JSON (great for machines / Power
# Automate, but ugly for humans). This endpoint returns a full HTML PAGE that a
# browser renders as a proper dashboard: KPI cards, a risk doughnut chart, and a
# vendor table.
#
# How it works:
#   1. The browser requests GET /dashboard-view.
#   2. FastAPI returns the HTML string below (as an HTMLResponse).
#   3. The JavaScript inside that page calls the JSON endpoint GET /dashboard
#      (same server, so no CORS issues) and paints the numbers into the page.
#   4. Because it fetches live, the page reflects new uploads whenever you reload.
#
# We keep all HTML/CSS/JS in one string so the project stays a single-file
# backend with no separate template engine to configure.

DASHBOARD_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Contract Intelligence Dashboard</title>
  <!-- Chart.js is loaded from a CDN and draws the risk doughnut chart. -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    /* --- Basic theme (enterprise blue, matching the documentation) --- */
    :root { --brand:#2E5A8C; --high:#d9534f; --med:#f0ad4e; --low:#5cb85c; --unk:#9aa4b2; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: Segoe UI, Roboto, Helvetica, Arial, sans-serif;
           background:#f5f7fa; color:#1f2933; }
    header { background:var(--brand); color:#fff; padding:20px 28px; }
    header h1 { margin:0; font-size:22px; }
    header p { margin:4px 0 0; opacity:.85; font-size:13px; }
    main { padding:24px 28px; max-width:1100px; margin:0 auto; }
    /* --- KPI cards row --- */
    .cards { display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin-bottom:24px; }
    .card { background:#fff; border-radius:10px; padding:16px; box-shadow:0 1px 3px rgba(0,0,0,.08);
            border-top:4px solid var(--brand); }
    .card .num { font-size:30px; font-weight:700; }
    .card .label { font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:#69707a; }
    .card.high { border-top-color:var(--high); }
    .card.med  { border-top-color:var(--med); }
    .card.low  { border-top-color:var(--low); }
    .card.unk  { border-top-color:var(--unk); }
    /* --- Two-column layout: chart + vendor table --- */
    .grid { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
    .panel { background:#fff; border-radius:10px; padding:18px; box-shadow:0 1px 3px rgba(0,0,0,.08); }
    .panel h2 { margin:0 0 12px; font-size:15px; color:var(--brand); }
    table { width:100%; border-collapse:collapse; font-size:14px; }
    th, td { text-align:left; padding:8px 10px; border-bottom:1px solid #eef1f5; }
    th { color:#69707a; font-weight:600; font-size:12px; text-transform:uppercase; }
    .btn { background:var(--brand); color:#fff; border:0; padding:8px 14px; border-radius:6px;
           cursor:pointer; font-size:13px; }
    .muted { color:#69707a; font-size:12px; }
    @media (max-width:800px){ .cards{grid-template-columns:repeat(2,1fr)} .grid{grid-template-columns:1fr} }
  </style>
</head>
<body>
  <header>
    <h1>Contract Intelligence Dashboard</h1>
    <p>Live view of the AI-analyzed contract portfolio &middot; data from GET /dashboard</p>
  </header>

  <main>
    <!-- KPI cards. The numbers start as "-" and are filled in by JavaScript. -->
    <div class="cards">
      <div class="card"><div class="num" id="total">-</div><div class="label">Total contracts</div></div>
      <div class="card high"><div class="num" id="high">-</div><div class="label">High risk</div></div>
      <div class="card med"><div class="num" id="med">-</div><div class="label">Medium risk</div></div>
      <div class="card low"><div class="num" id="low">-</div><div class="label">Low risk</div></div>
      <div class="card unk"><div class="num" id="unk">-</div><div class="label">Unknown</div></div>
    </div>

    <div class="grid">
      <div class="panel">
        <h2>Risk distribution</h2>
        <canvas id="riskChart" height="220"></canvas>
      </div>
      <div class="panel">
        <h2>Vendors by risk</h2>
        <table>
          <thead><tr><th>Vendor</th><th>Contracts</th><th>High</th><th>Avg risk</th></tr></thead>
          <tbody id="vendorRows"><tr><td class="muted" colspan="4">Loading...</td></tr></tbody>
        </table>
      </div>
    </div>

    <p style="margin-top:20px">
      <button class="btn" onclick="loadData()">Refresh</button>
      <span class="muted" id="updated"></span>
    </p>
  </main>

  <script>
    let chart;  // holds the Chart.js instance so we can update it on refresh

    // loadData() fetches the JSON from /dashboard and paints it into the page.
    async function loadData() {
      // 1. Call the JSON endpoint on the same server.
      const res  = await fetch('/dashboard');
      const data = await res.json();

      // 2. Fill the KPI cards.
      document.getElementById('total').textContent = data.total_contracts ?? 0;
      document.getElementById('high').textContent  = data.high_risk ?? 0;
      document.getElementById('med').textContent   = data.medium_risk ?? 0;
      document.getElementById('low').textContent   = data.low_risk ?? 0;
      document.getElementById('unk').textContent   = data.unknown_risk ?? 0;

      // 3. Draw / update the doughnut chart of risk levels.
      const values = [data.high_risk||0, data.medium_risk||0, data.low_risk||0, data.unknown_risk||0];
      const cfg = {
        type: 'doughnut',
        data: {
          labels: ['High', 'Medium', 'Low', 'Unknown'],
          datasets: [{ data: values,
            backgroundColor: ['#d9534f', '#f0ad4e', '#5cb85c', '#9aa4b2'] }]
        },
        options: { plugins: { legend: { position: 'bottom' } } }
      };
      if (chart) { chart.data.datasets[0].data = values; chart.update(); }
      else { chart = new Chart(document.getElementById('riskChart'), cfg); }

      // 4. Build the vendor table from /vendor-analytics (already ranked by risk).
      //    Each row shows the vendor, their contract count, how many are High,
      //    and the average risk severity (3 = all high, 1 = all low).
      const vres  = await fetch('/vendor-analytics');
      const vdata = await vres.json();
      const vendors = vdata.vendors || [];
      const tbody = document.getElementById('vendorRows');
      tbody.innerHTML = vendors.length
        ? vendors.map(v => `<tr>
            <td>${v.vendor}</td>
            <td>${v.total}</td>
            <td style="color:${v.high>0?'#d9534f':'#69707a'};font-weight:${v.high>0?'700':'400'}">${v.high}</td>
            <td>${v.avg_risk}</td>
          </tr>`).join('')
        : '<tr><td class="muted" colspan="4">No contracts yet</td></tr>';

      // 5. Timestamp so you know the view is live.
      document.getElementById('updated').textContent =
        'Updated ' + new Date().toLocaleTimeString();
    }

    loadData();  // run once on page load
  </script>
</body>
</html>
"""


@app.get("/dashboard-view", response_class=HTMLResponse)
def dashboard_view():
    # Return the HTML page. FastAPI sends it with Content-Type: text/html,
    # so the browser renders it instead of showing raw text.
    return HTMLResponse(content=DASHBOARD_PAGE)


@app.post("/health-test")
def health_test():

    return {
        "status": "working"
    }