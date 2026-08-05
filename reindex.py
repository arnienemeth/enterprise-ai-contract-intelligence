"""
Reindex the local vector store from the files in documents/.

Why: the contracts already in the vector store were ingested by the old
/upload-contract code, which hardcoded vendor="ACME" and risk_level="High".
This script re-embeds each document and stores the REAL vendor / risk level
returned by the AI, so the dashboard and semantic search reflect reality.

Usage (run from the project root, with .env configured):

    python reindex.py            # add documents/ to the store
    python reindex.py --reset    # wipe the store first, then re-ingest (recommended)

Requires a working Azure OpenAI configuration in .env (chat + embeddings).
"""

import os
import sys
import glob
import json

from dotenv import load_dotenv
from openai import AzureOpenAI

from vector_store.embedding_engine import add_document, reset_collection
from ingestion import extract_text, ExtractionError, SUPPORTED_EXTENSIONS

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

DOCUMENTS_DIR = "documents"


def analyze_contract(text: str) -> dict:
    """Ask the AI to extract the vendor and risk level from a contract."""

    # Cap the text sent to the analysis prompt; the full text is still chunked
    # and stored for retrieval elsewhere.
    analysis_text = text[:60000]

    prompt = f"""
Analyze this enterprise contract.

Identify:
- vendor / counterparty name (extract from the contract text)
- overall risk score (0-100)
- risk level (Low / Medium / High)

Contract:
{analysis_text}

Return ONLY valid JSON in this exact format:

{{
    "vendor": "vendor name or Unknown",
    "risk_score": 75,
    "risk_level": "High"
}}
"""

    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {
                "role": "system",
                "content": "You are a senior enterprise contract risk analyst. Return ONLY valid JSON. No markdown.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    raw = response.choices[0].message.content.strip()

    # Tolerate accidental ```json code fences
    if raw.startswith("```"):
        raw = raw.lstrip("`")
        if raw[:4].lower() == "json":
            raw = raw[4:]
        raw = raw.strip().rstrip("`").strip()

    try:
        return json.loads(raw)
    except Exception:
        return {"vendor": "Unknown", "risk_score": None, "risk_level": "Unknown"}


def main():
    do_reset = "--reset" in sys.argv

    if do_reset:
        reset_collection()

    # Ingest every supported format (PDF / DOCX / TXT / MD). Skip the legacy
    # double-extension ".txt.txt" copies.
    all_files = sorted(glob.glob(os.path.join(DOCUMENTS_DIR, "*")))
    files = [
        f for f in all_files
        if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
        and not f.endswith(".txt.txt")
    ]

    if not files:
        print(f"No documents found in {DOCUMENTS_DIR}/")
        return

    print(f"Reindexing {len(files)} document(s) from {DOCUMENTS_DIR}/ ...\n")

    for path in files:
        try:
            with open(path, "rb") as f:
                text = extract_text(f.read(), os.path.basename(path)).strip()
        except ExtractionError as e:
            print(f"  skip ({e}): {os.path.basename(path)}")
            continue

        if not text:
            print(f"  skip (empty): {path}")
            continue

        data = analyze_contract(text)
        vendor = str(data.get("vendor", "Unknown")).strip() or "Unknown"
        risk_level = str(data.get("risk_level", "Unknown")).strip() or "Unknown"

        add_document(
            text=text,
            filename=os.path.basename(path),
            vendor=vendor,
            risk_level=risk_level,
        )

        print(f"  indexed: {os.path.basename(path):32}  vendor={vendor:20}  risk={risk_level}")

    print("\nDone. Check results with:  GET /dashboard")


if __name__ == "__main__":
    main()
