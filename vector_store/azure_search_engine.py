"""Azure AI Search vector-store backend.

Implements the same interface as the ChromaDB backend (add_document,
search_similar, get_collection_stats, get_all_metadata, reset_collection) so the
rest of the app is unchanged. Activated when AZURE_SEARCH_ENDPOINT is set.

Config (environment variables):
    AZURE_SEARCH_ENDPOINT   https://<service>.search.windows.net
    AZURE_SEARCH_KEY        admin key for the search service
    AZURE_SEARCH_INDEX      index name (default: "contracts")
"""

import os
import uuid

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
)
from azure.search.documents.models import VectorizedQuery

from vector_store.embeddings_client import create_embedding

ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX", "contracts")

_credential = AzureKeyCredential(KEY)
_index_client = SearchIndexClient(endpoint=ENDPOINT, credential=_credential)
_search_client = SearchClient(endpoint=ENDPOINT, index_name=INDEX_NAME, credential=_credential)

_index_ready = False


def _ensure_index():
    """Create the search index (with a vector field) if it doesn't exist yet.

    Runs lazily on first use so importing this module never makes a network call.
    """
    global _index_ready
    if _index_ready:
        return

    existing = [i.name for i in _index_client.list_indexes()]
    if INDEX_NAME not in existing:
        # Size the vector field to match the embedding model's output.
        dim = len(create_embedding("dimension probe"))

        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
            SimpleField(name="filename", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="vendor", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="risk_level", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SearchField(
                name="embedding",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=dim,
                vector_search_profile_name="vprofile",
            ),
        ]

        vector_search = VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
            profiles=[VectorSearchProfile(name="vprofile", algorithm_configuration_name="hnsw")],
        )

        _index_client.create_index(
            SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search)
        )
        print(f"Created Azure AI Search index '{INDEX_NAME}' (dim={dim}).")

    _index_ready = True


def add_document(text, filename="unknown.txt", vendor="Unknown", risk_level="Unknown"):
    _ensure_index()

    embedding = create_embedding(text)
    doc_id = str(uuid.uuid4())

    _search_client.upload_documents(documents=[{
        "id": doc_id,
        "content": text,
        "filename": filename,
        "vendor": vendor,
        "risk_level": risk_level,
        "embedding": embedding,
    }])

    print(f"Document stored in Azure AI Search: {filename}")
    return {"document_id": doc_id, "filename": filename, "status": "stored"}


def search_similar(query, top_k=3):
    _ensure_index()

    query_embedding = create_embedding(query)
    vector_query = VectorizedQuery(
        vector=query_embedding, k_nearest_neighbors=top_k, fields="embedding"
    )

    results = _search_client.search(
        search_text=None,
        vector_queries=[vector_query],
        select=["content", "filename", "vendor", "risk_level"],
        top=top_k,
    )

    formatted = []
    for r in results:
        formatted.append({
            "text": r.get("content", ""),
            "filename": r.get("filename", "unknown"),
            "vendor": r.get("vendor", "Unknown"),
            "risk_level": r.get("risk_level", "Unknown"),
            "score": round(float(r.get("@search.score", 0.0)), 3),
        })
    return formatted


def get_all_metadata():
    _ensure_index()

    results = _search_client.search(
        search_text="*",
        select=["filename", "vendor", "risk_level"],
        top=1000,
    )
    return [
        {
            "filename": r.get("filename"),
            "vendor": r.get("vendor"),
            "risk_level": r.get("risk_level"),
        }
        for r in results
    ]


def get_collection_stats():
    metadatas = get_all_metadata()

    total = len(metadatas)
    counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    vendors = {}

    for meta in metadatas:
        level = str(meta.get("risk_level", "")).strip().lower()
        counts[level if level in counts else "unknown"] += 1

        vendor = str(meta.get("vendor", "Unknown")).strip() or "Unknown"
        vendors[vendor] = vendors.get(vendor, 0) + 1

    return total, counts, vendors


def reset_collection():
    """Remove every document from the index (keeps the index itself)."""
    _ensure_index()

    ids = [r["id"] for r in _search_client.search(search_text="*", select=["id"], top=1000)]
    if ids:
        _search_client.delete_documents(documents=[{"id": i} for i in ids])
        print(f"Azure AI Search index cleared ({len(ids)} document(s) removed).")

    return True
