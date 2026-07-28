from openai import AzureOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

print("Loading environment variables...")

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

print("Connecting to Azure OpenAI...")

response = client.chat.completions.create(
    model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
    messages=[
        {
            "role": "user",
            "content": "Explain MCP servers in simple words."
        }
    ],
    temperature=0.3
)

print("\\nAI RESPONSE:\\n")
print(response.choices[0].message.content)