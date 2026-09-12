import chromadb
client = chromadb.PersistentClient(path="~/Dev/Kenbun/brain_health/chromadb_local")

try:
    print("=== THE 2 SURVIVING CONCEPTS ===")
    col = client.get_collection("kenbun-agent.concepts")
    results = col.get()
    for doc, meta in zip(results['documents'], results['metadatas']):
        title = meta.get("title", "Unknown") if meta else "Unknown"
        print(f"Title: {title}")
        print(f"Content: {doc[:200]}...\n")
except Exception as e:
    print(f"Error reading concepts: {e}")

try:
    print("=== SAMPLING FROM 'kenbun-agent.concepts_qjl' (151 items) ===")
    col_qjl = client.get_collection("kenbun-agent.concepts_qjl")
    results_qjl = col_qjl.get()
    for doc, meta in zip(results_qjl['documents'][:5], results_qjl['metadatas'][:5]):
        title = meta.get("title", "Unknown") if meta else "Unknown"
        print(f"Title: {title}")
        print(f"Content: {doc[:200]}...\n")
except Exception as e:
    print(f"Error reading concepts_qjl: {e}")
