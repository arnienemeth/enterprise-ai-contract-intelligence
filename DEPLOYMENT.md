# Deployment Guide — Azure Container Apps

Deploy the platform to a live, public HTTPS URL on **Azure Container Apps**. The image is
built **in the cloud** (`az acr build`), so you don't need Docker installed locally. The
easiest way to run these commands is **Azure Cloud Shell** (bash) — no local setup at all.

---

## What you'll end up with

A URL like `https://contract-ai-api.<region>.azurecontainerapps.io` serving:
- `/dashboard-view` — the live dashboard (shows data immediately from the seed vector store)
- `/docs` — Swagger UI
- all API endpoints

---

## Prerequisites

- An Azure subscription.
- Your **rotated** Azure OpenAI key (you'll paste it once, as a secret).
- Your repo pushed to GitHub (public): `https://github.com/arnienemeth/enterprise-ai-contract-intelligence`

---

## Step 1 — Open Azure Cloud Shell

1. Go to **https://portal.azure.com** and click the **Cloud Shell** icon (`>_`) in the top bar.
2. Choose **Bash** if prompted. (It has `az` and `git` preinstalled.)

## Step 2 — Clone your repo

```bash
git clone https://github.com/arnienemeth/enterprise-ai-contract-intelligence.git
cd enterprise-ai-contract-intelligence
```

## Step 3 — Set variables

Edit `ACR` to something globally unique (lowercase letters/numbers only).

```bash
RG=rg-contract-ai
LOCATION=westeurope
ACR=contractaiacr$RANDOM
ENVNAME=contract-ai-env
APP=contract-ai-api
```

## Step 4 — Create the resource group and container registry

```bash
az group create -n $RG -l $LOCATION

az acr create -n $ACR -g $RG --sku Basic --admin-enabled true
```

## Step 5 — Build the image in the cloud

```bash
az acr build -r $ACR -t contract-ai:v1 .
```

This uploads the code and builds the Docker image on Azure — no local Docker needed.

## Step 6 — Create the Container Apps environment

```bash
az extension add --name containerapp --upgrade -y
az provider register -n Microsoft.App --wait
az provider register -n Microsoft.OperationalInsights --wait

az containerapp env create -n $ENVNAME -g $RG -l $LOCATION
```

## Step 7 — Deploy the app

Replace `PASTE_YOUR_ROTATED_KEY_HERE` with your Azure OpenAI key. The key is stored as a
**secret** and referenced by the app — it never appears in plain text in the config.

```bash
ACR_SERVER=$(az acr show -n $ACR --query loginServer -o tsv)
ACR_USER=$(az acr credential show -n $ACR --query username -o tsv)
ACR_PASS=$(az acr credential show -n $ACR --query 'passwords[0].value' -o tsv)

az containerapp create \
  -n $APP -g $RG --environment $ENVNAME \
  --image $ACR_SERVER/contract-ai:v1 \
  --registry-server $ACR_SERVER --registry-username $ACR_USER --registry-password $ACR_PASS \
  --target-port 8000 --ingress external \
  --min-replicas 1 --max-replicas 1 \
  --secrets openai-key="PASTE_YOUR_ROTATED_KEY_HERE" \
  --env-vars \
    AZURE_OPENAI_API_KEY=secretref:openai-key \
    AZURE_OPENAI_ENDPOINT="https://rg-enterprise-ai-demo.openai.azure.com/" \
    AZURE_OPENAI_API_VERSION="2024-10-21" \
    AZURE_OPENAI_DEPLOYMENT="gpt-4o-mini" \
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT="embedding-test"
```

## Step 8 — Get your live URL

```bash
echo "https://$(az containerapp show -n $APP -g $RG --query properties.configuration.ingress.fqdn -o tsv)"
```

Open that URL and add **`/dashboard-view`** — you should see the live dashboard.
Try **`/docs`** for Swagger, and test `/ask` to confirm the Azure OpenAI key works.

---

## Updating after code changes

```bash
git pull
az acr build -r $ACR -t contract-ai:v2 .
az containerapp update -n $APP -g $RG --image $ACR_SERVER/contract-ai:v2
```

## Notes

- **Cost:** `--min-replicas 1` keeps one instance warm (small ongoing cost, no cold starts).
  Set `--min-replicas 0` to scale to zero and pay almost nothing, at the cost of a cold start
  on the first request.
- **Data:** the dashboard and vendor analytics render from the committed seed vector store and
  need no Azure calls. Contract uploads at runtime are stored in the container and reset on
  restart — persistent writes come later with Azure AI Search (see ROADMAP.md).
- **Security:** the API is currently open (no auth). Adding Microsoft Entra ID protection is
  the next production-hardening step (see ROADMAP.md).
- **Clean up** (to stop all charges): `az group delete -n $RG --yes --no-wait`
```
