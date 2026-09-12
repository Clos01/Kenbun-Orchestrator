import chromadb
from chromadb.config import Settings
client = chromadb.HttpClient(host="127.0.0.1", port=8000)
try:
    collections = client.list_collections()
    print(f"Collections on Mac (127.0.0.1): {[c.name for c in collections]}")
    for col in collections:
        if col.name == "concepts":
            results = col.get()
            print(f"--- Total Concepts Found on Mac: {len(results['documents'])} ---")
            for doc, meta in zip(results['documents'][:5], results['metadatas'][:5]):
                title = meta.get("title", "Unknown") if meta else "Unknown"
                print(f"- {title}: {doc[:50]}...")
except Exception as e:
    print(f"Error connecting to local Mac ChromaDB: {e}")
