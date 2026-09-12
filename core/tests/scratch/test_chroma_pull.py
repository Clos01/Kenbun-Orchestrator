import sys
import chromadb
try:
    client = chromadb.HttpClient(host="127.0.0.1", port=8000)
    collections = client.list_collections()
    for col in collections:
        if col.name == "kenbun-agent.concepts":
            results = col.get()
            print(f"--- Total Concepts Found on Mac (127.0.0.1): {len(results['documents'])} ---")
            for doc, meta in zip(results['documents'][:5], results['metadatas'][:5]):
                title = meta.get("title", "Unknown") if meta else "Unknown"
                print(f"- {title}: {doc[:50]}...")
except Exception as e:
    print(f"Error: {e}")
