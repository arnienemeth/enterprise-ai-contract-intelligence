"""Shared Azure OpenAI embedding client.

Kept in its own module so both vector-store backends (ChromaDB and Azure AI
Search) can create embeddings without importing each other (avoids circular
imports)."""

import os

from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)


def create_embedding(text):
    """Turn text into a vector using the Azure OpenAI embedding deployment."""
    response = client.embeddings.create(
        model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        input=[text],
    )
    return response.data[0].embedding
