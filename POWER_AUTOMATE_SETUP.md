# SharePoint + Power Automate Integration Guide

This connects the enterprise front end to the live AI API. When a contract file is
dropped into a SharePoint library, Power Automate sends it to the deployed API, gets back
the AI risk analysis, and writes the results into a SharePoint "Contract Register" list
(plus an optional Teams alert).

```text
SharePoint (file uploaded)
   -> Power Automate: Get file content
   -> HTTP POST  https://<your-app>/analyze-contract   (X-API-Key header)
   -> Receive AI JSON (vendor, risk_score, risk_level, summary, ...)
   -> Create item in the Contract Register list
   -> (optional) Post a Teams message
```

The API side is already built and deployed: **`POST /analyze-contract`** accepts JSON
`{ "filename": "...", "content": "..." }` with the `X-API-Key` header and returns the
structured risk JSON. This guide covers only the Microsoft 365 side.

---

## Prerequisites

- A SharePoint site you can create lists/libraries in.
- Power Automate with the **premium HTTP action** (the generic `HTTP` connector is
  premium; a 90-day Power Automate Premium trial works if you don't have a license).
- Your deployed API URL and your **API key** (the one you set as the container secret).
- Note: this flow handles **text (.txt)** contracts. PDF/Word need OCR first
  (Azure AI Document Intelligence — a later roadmap step).

---

## Step 1 — Create the SharePoint objects

**1a. Contracts library (where files land)**
On your SharePoint site: **New → Document library** → name it **Contracts**.

**1b. Contract Register list (where AI results are written)**
**New → List** → name it **Contract Register**, then add these columns
(**Settings → List settings → Create column**):

| Column | Type |
|--------|------|
| Vendor | Single line of text |
| RiskScore | Number |
| RiskLevel | Choice (Low, Medium, High, Unknown) |
| ExecutiveSummary | Multiple lines of text |
| FinancialRisk | Multiple lines of text |
| ComplianceRisk | Multiple lines of text |
| LiabilityRisk | Multiple lines of text |
| OperationalRisk | Multiple lines of text |
| FileName | Single line of text |
| Status | Choice (New, Reviewed) |

(The built-in **Title** column is reused for the contract name.)

---

## Step 2 — Build the Power Automate flow

Go to **make.powerautomate.com → Create → Automated cloud flow**.
Name it "Contract AI Analysis" and pick the trigger **"When a file is created (properties only)"** (SharePoint).

**2.1 Trigger — When a file is created (properties only)**
- Site Address: your site
- Library Name: **Contracts**

**2.2 Action — Get file content** (SharePoint)
- Site Address: your site
- File Identifier: from the trigger, choose **Identifier**

**2.3 Action — Compose** (decode the file to text)
Name it `ContractText`. In the Inputs box, paste this expression (Expression tab):
```
base64ToString(body('Get_file_content')?['$content'])
```

**2.4 Action — HTTP** (call the AI API)
- Method: **POST**
- URI: `https://<YOUR-APP>.azurecontainerapps.io/analyze-contract`
- Headers:
  - `Content-Type` : `application/json`
  - `X-API-Key` : `<YOUR-API-KEY>`
- Body:
```json
{
  "filename": "@{triggerOutputs()?['body/{FilenameWithExtension}']}",
  "content": "@{outputs('ContractText')}"
}
```

**2.5 Action — Parse JSON** (read the AI response)
- Content: the **Body** of the HTTP action
- Schema:
```json
{
  "type": "object",
  "properties": {
    "vendor": { "type": "string" },
    "risk_score": { "type": "number" },
    "risk_level": { "type": "string" },
    "financial_risk": { "type": "string" },
    "compliance_risk": { "type": "string" },
    "liability_risk": { "type": "string" },
    "operational_risk": { "type": "string" },
    "executive_summary": { "type": "string" },
    "filename": { "type": "string" }
  }
}
```

**2.6 Action — Create item** (SharePoint, write to the register)
- Site Address: your site
- List Name: **Contract Register**
- Map the fields from the Parse JSON output:

| SharePoint column | Value (from Parse JSON) |
|-------------------|-------------------------|
| Title | `filename` |
| Vendor | `vendor` |
| RiskScore | `risk_score` |
| RiskLevel | `risk_level` |
| ExecutiveSummary | `executive_summary` |
| FinancialRisk | `financial_risk` |
| ComplianceRisk | `compliance_risk` |
| LiabilityRisk | `liability_risk` |
| OperationalRisk | `operational_risk` |
| FileName | `filename` |
| Status | `New` |

**2.7 (Optional) Action — Post message in a chat or channel** (Teams)
Post to a channel with a summary, e.g.:
```
New contract analyzed: @{body('Parse_JSON')?['vendor']}
Risk: @{body('Parse_JSON')?['risk_level']} (@{body('Parse_JSON')?['risk_score']}/100)
@{body('Parse_JSON')?['executive_summary']}
```

**Save the flow.**

---

## Step 3 — Test

1. Upload one of the sample contracts from `documents/` (e.g. `saas_datapeak.txt`) into the
   **Contracts** library.
2. Watch the flow run (Power Automate → your flow → run history).
3. Open the **Contract Register** list — a new row should appear with the AI's vendor, risk
   score/level, and executive summary. If you added the Teams step, you'll get a message too.

---

## Troubleshooting

- **HTTP 401 from the API** → the `X-API-Key` header is missing or wrong.
- **HTTP action is greyed out / asks for a plan** → it's a premium connector; start a Power
  Automate Premium trial or use a licensed environment.
- **`content` looks like gibberish** → the file wasn't decoded; re-check the `base64ToString`
  expression in the Compose step.
- **Empty vendor / "Unknown"** → the AI couldn't find a vendor name in that file (expected for
  very short or generic documents).
- **Non-.txt files** → this flow expects text. PDFs/Word need OCR (Azure AI Document
  Intelligence) before the text can be analyzed — a later roadmap item.

---

## Security note

The API key travels in the `X-API-Key` header from Power Automate. Keep it in the flow only
(don't expose it in the SharePoint list or a public place). If it leaks, rotate the container
secret and update the header in the flow.
