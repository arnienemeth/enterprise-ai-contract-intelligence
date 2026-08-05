"""Azure AI Search vector-store backend (chunk-aware).

Implements the same interface as the ChromaDB backend (add_document,
search_similar, get_collection_stats, get_all_metadata, reset_collection) so the
rest of the app is unchanged. Activated when AZURE_SEARCH_ENDPOINT is set.

Chunking model
--------------
A contract is split into overlapping chunks (see ingestion/chunker.py). Each
chunk is one row in the index, sharing the parent's ``doc_id`` and carrying its
own ``chunk_index``. Semantic search therefore retrieves the most relevant
*section*, while document-level stats (dashboard, vendor analytics) dedupe by
``doc_id`` so a 12-chunk contract still counts as one contract.

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
from ingestion.chunker import chunk_text

ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX", "contracts")

_credential = AzureKeyCredential(KEY)
_index_client = SearchIndexClient(endpoint=ENDPOINT, credential=_credential)
_search_client = SearchClient(endpoint=ENDPOINT, index_name=INDEX_NAME, credential=_credential)

_index_ready = False

# Fields the chunk-aware schema must have. If an existing index predates
# chunking (no "doc_id"), it is recreated so the schema is correct.
_REQUIRED_FIELDS = {"id", "content", "filename", "vendor", "risk_level", "doc_id", "chunk_index", "embedding"}


def _build_index() -> SearchIndex:
    # Size the vector field to match the embedding model's output (autodetected).
    dim = len(create_embedding("dimension probe"))

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
        SimpleField(name="filename", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="vendor", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="risk_level", type=SearchFieldDataType.String, filterable=True, facetable=True),
        # Chunking metadata.
        SimpleField(name="doc_id", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
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

    return SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search)


def _ensure_index():
    """Create (or upgrade) the search index. Runs lazily on first use.

    If an older index without the chunking fields exists, it is deleted and
    recreated with the correct schema (data must be re-ingested via reindex.py).
    """
    global _index_ready
    if _index_ready:
        return

    existing = {i.name: i for i in _index_client.list_indexes()}

    if INDEX_NAME in existing:
        field_names = {f.name for f in existing[INDEX_NAME].fields}
        if not _REQUIRED_FIELDS.issubset(field_names):
            print(
                f"Index '{INDEX_NAME}' is missing chunking fields "
                f"{_REQUIRED_FIELDS - field_names}; recreating."
            )
            _index_client.delete_index(INDEX_NAME)
            _index_client.create_index(_build_index())
            print(f"Recreated Azure AI Search index '{INDEX_NAME}' (chunk-aware).")
    else:
        _index_client.create_index(_build_index())
        print(f"Created Azure AI Search index '{INDEX_NAME}' (chunk-aware).")

    _index_ready = True


def add_document(text, filename="unknown.txt", vendor="Unknown", risk_level="Unknown"):
    """Chunk the document and store one vector row per chunk.

    All chunks share a generated ``doc_id`` so downstream aggregation counts the
    document once. Returns the doc_id and chunk count.
    """
    _ensure_index()

    chunks = chunk_text(text) or [text]
    doc_id = str(uuid.uuid4())

    documents = []
    for idx, chunk in enumerate(chunks):
        documents.append({
            "id": f"{doc_id}-{idx}",
            "content": chunk,
            "filename": filename,
            "vendor": vendor,
            "risk_level": risk_level,
            "doc_id": doc_id,
            "chunk_index": idx,
            "embedding": create_embedding(chunk),
        })

    _search_client.upload_documents(documents=documents)

    print(f"Stored in Azure AI Search: {filename} ({len(chunks)} chunk(s))")
    return {
        "document_id": doc_id,
        "filename": filename,
        "chunks": len(chunks),
        "status": "stored",
    }


def search_similar(query, top_k=5):
    _ensure_index()

    query_embedding = create_embedding(query)
    vector_query = VectorizedQuery(
        vector=query_embedding, k_nearest_neighbors=top_k, fields="embedding"
    )

    results = _search_client.search(
        search_text=None,
        vector_queries=[vector_query],
        select=["content", "filename", "vendor", "risk_level", "doc_id", "chunk_index"],
        top=top_k,
    )

    formatted = []
    for r in results:
        formatted.append({
            "text": r.get("content", ""),
            "filename": r.get("filename", "unknown"),
            "vendor": r.get("vendor", "Unknown"),
            "risk_level": r.get("risk_level", "Unknown"),
            "doc_id": r.get("doc_id"),
            "chunk_index": r.get("chunk_index"),
            "score": round(float(r.get("@search.score", 0.0)), 3),
        })
    return formatted


def _iter_all_chunk_metadata():
    """Yield metadata for every chunk row (used to derive document-level stats)."""
    results = _search_client.search(
        search_text="*",
        select=["doc_id", "filename", "vendor", "risk_level"],
        top=1000,
    )
    for r in results:
        yield r


def get_all_metadata():
    """Return one metadata record per *document* (deduped by doc_id).

    Legacy rows without a doc_id fall back to filename as the identity key, so a
    mixed index still counts documents sanely.
    """
    seen = {}
    for r in _iter_all_chunk_metadata():
        key = r.get("doc_id") or r.get("filename") or str(uuid.uuid4())
        if key not in seen:
            seen[key] = {
                "filename": r.get("filename"),
                "vendor": r.get("vendor"),
                "risk_level": r.get("risk_level"),
            }
    return list(seen.values())


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
    """Remove every chunk from the index (keeps the index itself)."""
    _ensure_index()

    ids = [r["id"] for r in _search_client.search(search_text="*", select=["id"], top=1000)]
    if ids:
        _search_client.delete_documents(documents=[{"id": i} for i in ids])
        print(f"Azure AI Search index cleared ({len(ids)} chunk(s) removed).")

    return True
