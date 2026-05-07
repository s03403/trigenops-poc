import json
from langchain_community.vectorstores import Chroma
from langchain_openai import AzureOpenAIEmbeddings
from langchain_core.documents import Document

# 1. Load logs
with open("tools/sample_logs.json") as f:
    logs = json.load(f)

# 2. Convert each log entry → one Document
documents = []
for entry in logs:
    # Combine message + details into page_content (what gets embedded)
    detail_lines = "\n".join(f"  {k}: {v}" for k, v in entry.get("details", {}).items())
    page_content = f"[{entry['severity']}] {entry['message']}\nDetails:\n{detail_lines}"

    # Structured fields → metadata (used for filtering, not embedded)
    metadata = {
        "log_id": entry["log_id"],
        "application": entry["application"],
        "source": entry["source"],
        "job_name": entry["job_name"],
        "severity": entry["severity"],
        "timestamp": entry["timestamp"],
    }

    documents.append(Document(page_content=page_content, metadata=metadata))

# 3. Create embeddings + store in Chroma
embeddings = AzureOpenAIEmbeddings(
    azure_deployment="text-embedding-ada-002",  # or your deployment name
    azure_endpoint="https://openai-ppcazure017.openai.azure.com/",
    api_key="373446e8af1a462fa4d245d9a92a7697",
    api_version="2024-08-01-preview",
)

vectorstore = Chroma.from_documents(
    documents,
    embeddings,
    persist_directory="vectorstore/chroma_logs",
    collection_name="observer_logs",
)

# 4. Query example — filter by application
results = vectorstore.similarity_search(
    "target frequency data missing",
    k=3,
    filter={"application": "ASCM"},  # per-app filtering
)

for doc in results:
    print(doc.metadata["log_id"], doc.metadata["severity"])
    print(doc.page_content[:200])
    print("---")