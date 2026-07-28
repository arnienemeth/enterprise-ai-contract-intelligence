from vector_store.embedding_engine import add_document, search_similar

add_document(
    "ACME contract contains high financial risk due to 120 day payment terms."
)

add_document(
    "Vendor agreement has medium compliance risk related to GDPR."
)

results = search_similar(
    "Which contract has payment risk?"
)

print(results)