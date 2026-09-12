import os
from dotenv import load_dotenv
load_dotenv("~/Dev/Kenbun/.env")
import chromadb

host = os.environ.get("CHROMA_HOST", "localhost")
port = os.environ.get("CHROMA_PORT", "8000")
print("Host:", host, "Port:", port)

try:
    client = chromadb.HttpClient(host=host, port=port)
    print("Heartbeat:", client.heartbeat())
except Exception as e:
    print("Error:", e)
