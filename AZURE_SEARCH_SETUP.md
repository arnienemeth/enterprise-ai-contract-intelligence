# Azure AI Search Setup

Switches the vector store from local ChromaDB to **Azure AI Search** — a managed,
persistent vector database. The code auto-detects it: when `AZURE_SEARCH_ENDPOINT` is set,
the app uses Azure AI Search; otherwise it uses ChromaDB. No code changes are needed to
switch — just configuration.

Result: the deployed app becomes **stateful** — uploaded contracts persist across container
restarts (instead of the ephemeral in-container Chroma store).

---

## Order of operations

1. Push the code (adds the Azure Search backend + dependency) → CI/CD redeploys. *Still on
   Chroma until step 4.*
2. Create the Azure AI Search service.
3. Seed the index with your contracts.
4. Point the container at Azure AI Search → it switches over.

---

## Step 1 — Push the code

```powershell
git add vector_store/ requirements.txt .env.example AZURE_SEARCH_SETUP.md README.md PROJECT_STATUS.md
git commit -m "Add Azure AI Search backend (config-switchable vector store)"
git push
```

CI/CD rebuilds the image (now including `azure-search-documents`). Behavior is unchanged until
you set the env vars in step 4.

## Step 2 — Create the search service (Cloud Shell)

The **Free** tier is enough for this demo (supports vector search; one free service per
subscription; no cost).

```bash
RG=rg-contract-ai
SEARCH=contractaisearch$RANDOM     # must be globally unique, lowercase

az search service create -n "$SEARCH" -g "$RG" --sku free --location westeurope

SEARCH_ENDPOINT="https://$SEARCH.search.windows.net"
SEARCH_KEY=$(az search admin-key show --service-name "$SEARCH" -g "$RG" --query primaryKey -o tsv)

echo "ENDPOINT: $SEARCH_ENDPOINT"
echo "KEY:      $SEARCH_KEY"
```

Copy the ENDPOINT and KEY — you'll need them next. (Provisioning takes a couple of minutes.)

## Step 3 — Seed the index with your contracts

Run the reindex **once** against Azure AI Search. Easiest on your local machine:

1. Add these lines to your local `.env` (use the values from step 2):
   ```
   AZURE_SEARCH_ENDPOINT=https://<your-search>.search.windows.net
   AZURE_SEARCH_KEY=<your-search-admin-key>
   AZURE_SEARCH_INDEX=contracts
   ```
2. Install the new dependency and run the reindex:
   ```powershell
   pip install -r requirements.txt
   python reindex.py --reset
   ```
   The script now writes to Azure AI Search (it prints "Vector store backend: Azure AI Search").
   It creates the `contracts` index automatically and uploads all 19 contracts.

> Prefer not to touch local `.env`? You can instead run these same steps in Cloud Shell after
> `git clone` + `pip install -r requirements.txt`, exporting the two variables first.

## Step 4 — Point the deployed app at Azure AI Search

```bash
RG=rg-contract-ai
APP=contract-ai-api

az containerapp secret set -n "$APP" -g "$RG" --secrets search-key="$SEARCH_KEY"

az containerapp update -n "$APP" -g "$RG" \
  --set-env-vars \
    AZURE_SEARCH_ENDPOINT="$SEARCH_ENDPOINT" \
    AZURE_SEARCH_KEY=secretref:search-key \
    AZURE_SEARCH_INDEX=contracts
```

The app restarts and now reads/writes Azure AI Search. Open `…/dashboard-view` — it shows the
same contracts, now served from the managed index. Uploads via `/upload-contract` and
`/analyze-contract` now **persist**.

---

## Verify

- `…/dashboard` → returns your contract counts (from Azure AI Search).
- `…/ask` (with the API key) → returns grounded answers using Azure AI Search vector results.
- In the Azure Portal → your search service → **Indexes → contracts** → you can see the
  documents and even run test queries.

## Rollback

To go back to the in-container ChromaDB, remove the search env vars:
```bash
az containerapp update -n contract-ai-api -g rg-contract-ai \
  --remove-env-vars AZURE_SEARCH_ENDPOINT AZURE_SEARCH_KEY AZURE_SEARCH_INDEX
```

## Notes

- **Free tier limits:** 50 MB, 3 indexes, no SLA — fine for a demo. Move to **Basic**/**Standard**
  for real workloads.
- **Cost:** the Free tier is free. Basic is a paid, always-on service — remember it when
  estimating monthly cost.
- **Security:** the admin key is stored as a container secret (`search-key`), not in plain text.
