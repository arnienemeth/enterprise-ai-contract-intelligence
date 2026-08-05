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

    from ingestion.chunker import chunk_text

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
        """Chunk the document and store one embedding per chunk.

        All chunks share a generated doc_id so document-level stats count the
        contract once even though it lives as several vectors."""
        chunks = chunk_text(text) or [text]
        doc_id = str(uuid.uuid4())

        ids, embeddings, documents, metadatas = [], [], [], []
        for idx, chunk in enumerate(chunks):
            ids.append(f"{doc_id}-{idx}")
            embeddings.append(create_embedding(chunk))
            documents.append(chunk)
            metadatas.append({
                "filename": filename,
                "vendor": vendor,
                "risk_level": risk_level,
                "doc_id": doc_id,
                "chunk_index": idx,
            })

        collection.add(
            documents=documents,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas,
        )
        print(f"Document stored: {filename} ({len(chunks)} chunk(s))")
        return {
            "document_id": doc_id,
            "filename": filename,
            "chunks": len(chunks),
            "status": "stored",
        }

    def search_similar(query, top_k=5):
        query_embedding = create_embedding(query)
        results = collection.query(query_embeddings=[query_embedding], n_results=top_k)

        formatted_results = []
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for i in range(len(documents)):
            meta = metadatas[i] or {}
            formatted_results.append({
                "text": documents[i],
                "filename": meta.get("filename", "unknown"),
                "vendor": meta.get("vendor", "Unknown"),
                "risk_level": meta.get("risk_level", "Unknown"),
                "doc_id": meta.get("doc_id"),
                "chunk_index": meta.get("chunk_index"),
                "score": round(1 - distances[i], 3),
            })
        return formatted_results

    def _dedupe_by_document(metadatas):
        """Collapse chunk-level metadata to one record per document (by doc_id)."""
        seen = {}
        for meta in metadatas:
            meta = meta or {}
            key = meta.get("doc_id") or meta.get("filename") or str(uuid.uuid4())
            if key not in seen:
                seen[key] = {
                    "filename": meta.get("filename"),
                    "vendor": meta.get("vendor"),
                    "risk_level": meta.get("risk_level"),
                }
        return list(seen.values())

    def get_collection_stats():
        """Aggregate real counts from the collection. Returns (total, counts, vendors).

        Deduped by doc_id so chunks of the same contract count once."""
        data = collection.get(include=["metadatas"])
        metadatas = _dedupe_by_document(data.get("metadatas") or [])

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
        """Return one metadata record per document (deduped by doc_id)."""
        data = collection.get(include=["metadatas"])
        return _dedupe_by_document(data.get("metadatas") or [])
