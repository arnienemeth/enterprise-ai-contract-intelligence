from openai import AzureOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

print(os.getenv("AZURE_OPENAI_ENDPOINT"))
print(os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"))

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-10-21",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

response = client.embeddings.create(
    model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
    input=["hello world"]
)

print(response.data[0].embedding[:5])