"""Vector-store dispatcher.

Exposes a single interface — add_document, search_similar, get_collection_stats,
get_all_metadata, reset_collection — backed by either:

  * Azure AI Search   (production)  — used when AZURE_SEARCH_ENDPOINT is set
  * ChromaDB          (local dev)   — the default

The rest of the app imports from this module and doesn't care which backend is
active, so switching is a config change, not a code change.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# Shared embedding client (used by both backends).
from vector_store.embeddings_client import create_embedding  # noqa: F401 (re-exported)


if os.getenv("AZURE_SEARCH_ENDPOINT"):
    # ---- Production backend: Azure AI Search ----
    print("Vector store backend: Azure AI Search")
    from vector_store.azure_search_engine import (  # noqa: F401
        add_document,
        search_similar,
        get_collection_stats,
        get_all_metadata,
        reset_collection,
    )

else:
    # ---- Local backend: ChromaDB ----
    print("Vector store backend: ChromaDB (local)")

    import uuid
    import chromadb

    chroma_client = chromadb.PersistentClient(path="./vector_db")
    COLLECTION_NAME = "enterprise_knowledge"
    collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)

    def reset_collection():
        """Remove every document from the collection, keeping the collection itself.

        Clears documents *in place* rather than deleting/recreating the collection,
        so a running server keeps working (deleting would change the collection id).
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

    def add_document(text, filename="unknown.txt", vendor="Unknown", risk_level="Unknown"):
        embedding = create_embedding(text)
        doc_id = str(uuid.uuid4())
        collection.add(
            documents=[text],
            embeddings=[embedding],
            ids=[doc_id],
            metadatas=[{"filename": filename, "vendor": vendor, "risk_level": risk_level}],
        )
        print(f"Document stored: {filename}")
        return {"document_id": doc_id, "filename": filename, "status": "stored"}

    def search_similar(query, top_k=3):
        query_embedding = create_embedding(query)
        results = collection.query(query_embeddings=[query_embedding], n_results=top_k)

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
                "score": round(1 - distances[i], 3),
            })
        return formatted_results

    def get_collection_stats():
        """Aggregate real counts from the collection. Returns (total, counts, vendors)."""
        data = collection.get(include=["metadatas"])
        metadatas = data.get("metadatas") or []

        total = len(metadatas)
        counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
        vendors = {}

        for meta in metadatas:
            meta = meta or {}
            level = str(meta.get("risk_level", "")).strip().lower()
            counts[level if level in counts else "unknown"] += 1
            vendor = str(meta.get("vendor", "Unknown")).strip() or "Unknown"
            vendors[vendor] = vendors.get(vendor, 0) + 1

        return total, counts, vendors

    def get_all_metadata():
        """Return the metadata record for every document in the collection."""
        data = collection.get(include=["metadatas"])
        return data.get("metadatas") or []
