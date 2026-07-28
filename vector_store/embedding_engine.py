import chromadb
import uuid
import os

from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

# ==========================================
# CHROMA DB
# ==========================================

chroma_client = chromadb.PersistentClient(
    path="./vector_db"
)

COLLECTION_NAME = "enterprise_knowledge"

collection = chroma_client.get_or_create_collection(
    name=COLLECTION_NAME
)

# ==========================================
# RESET COLLECTION (for a clean reindex)
# ==========================================

def reset_collection():
    """Remove every document from the collection, keeping the collection itself.

    Used by reindex.py to clear embeddings created by the old code (which stored
    hardcoded vendor/risk metadata).

    NOTE: we clear documents *in place* rather than deleting and recreating the
    collection. Deleting the collection changes its id, which breaks any other
    process (e.g. a running uvicorn server) that still holds a handle to the old
    collection — it would raise "Collection [id] does not exist". Clearing in
    place keeps the id stable so a running server keeps working.
    """

    global collection

    try:
        existing = collection.get()
        ids = existing.get("ids", []) or []

        if ids:
            collection.delete(ids=ids)

        print(f"Vector store cleared ({len(ids)} document(s) removed).")

    except Exception as e:
        print(f"reset_collection warning: {e}")

    return True

# ==========================================
# CREATE EMBEDDING
# ==========================================

def create_embedding(text):

    response = client.embeddings.create(
        model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        input=[text]
    )

    return response.data[0].embedding

# ==========================================
# ADD DOCUMENT
# ==========================================

def add_document(
    text,
    filename="unknown.txt",
    vendor="Unknown",
    risk_level="Unknown"
):

    embedding = create_embedding(text)

    doc_id = str(uuid.uuid4())

    collection.add(
        documents=[text],
        embeddings=[embedding],
        ids=[doc_id],
        metadatas=[
            {
                "filename": filename,
                "vendor": vendor,
                "risk_level": risk_level
            }
        ]
    )

    print(f"Document stored: {filename}")

    return {
        "document_id": doc_id,
        "filename": filename,
        "status": "stored"
    }

# ==========================================
# SEARCH SIMILAR
# ==========================================

def search_similar(query, top_k=3):

    query_embedding = create_embedding(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    formatted_results = []

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for i in range(len(documents)):

        formatted_results.append({
            "text": documents[i],
            "filename": metadatas[i]["filename"],
            "vendor": metadatas[i]["vendor"],
            "risk_level": metadatas[i]["risk_level"],
            "score": round(1 - distances[i], 3)
        })

    return formatted_results

# ==========================================
# COLLECTION STATS (for /dashboard)
# ==========================================

def get_collection_stats():
    """Aggregate real counts from the ChromaDB collection.

    Returns (total, counts_by_level, counts_by_vendor).
    """

    data = collection.get(include=["metadatas"])

    metadatas = data.get("metadatas") or []

    total = len(metadatas)

    counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    vendors = {}

    for meta in metadatas:

        meta = meta or {}

        level = str(meta.get("risk_level", "")).strip().lower()

        if level in counts:
            counts[level] += 1
        else:
            counts["unknown"] += 1

        vendor = str(meta.get("vendor", "Unknown")).strip() or "Unknown"
        vendors[vendor] = vendors.get(vendor, 0) + 1

    return total, counts, vendors


# ==========================================
# RAW METADATA (for analytics)
# ==========================================

def get_all_metadata():
    """Return the metadata record for every document in the collection.

    Each item looks like {"filename": ..., "vendor": ..., "risk_level": ...}.
    Analytics endpoints build on this instead of re-querying Chroma themselves.
    """

    data = collection.get(include=["metadatas"])

    return data.get("metadatas") or []

