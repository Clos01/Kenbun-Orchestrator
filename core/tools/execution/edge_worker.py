"""
Edge_Node SFF Worker Node Client
============================
Dispatches CPU-bound AI tasks (embeddings, summarization, light inference)
to the Lenovo ThinkStation Edge_Node running Ollama.

The Edge_Node is our "Embeddings Specialist":
  - 32GB RAM: Can run 7B quantized models CPU-only
  - 2GB VRAM: NOT used for GPU inference (too small)
  - Role: Background tasks, embeddings, ChromaDB population

Usage:
    from tools.execution.p330_worker import p330_worker
    if p330_worker.is_online():
        embedding = p330_worker.embed("text to embed")
"""
import json
import logging
import requests
from typing import Optional
from tools.infrastructure.config import settings

logger = logging.getLogger(__name__)

P330_IP = settings.workers.p330_ip
P330_OLLAMA_PORT = settings.workers.p330_ollama_port
P330_BASE_URL = f"http://{P330_IP}:{P330_OLLAMA_PORT}"

# Best models for Edge_Node's 32GB RAM + CPU-only profile
EMBEDDING_MODEL = "nomic-embed-text"   # ~274MB — ultra-fast embeddings
LIGHT_CHAT_MODEL = "phi3:mini"         # 3.8B — fast on 32GB RAM at ~5 tok/s
SUMMARIZER_MODEL = "qwen2.5:7b"        # 7B quant — good summaries, ~3 tok/s


class P330Worker:
    """
    Lightweight task dispatcher for the Edge_Node CPU inference node.
    All tasks are fire-and-forget background jobs.
    Falls back gracefully if Edge_Node is offline.
    """

    def __init__(self, timeout: int = 10):
        self.base_url = P330_BASE_URL
        self.timeout = timeout

    def is_online(self) -> bool:
        """Ping the Edge_Node Ollama instance to check availability."""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def ping(self) -> dict:
        """Full health check — returns status and available models."""
        if not self.is_online():
            return {"status": "offline", "ip": P330_IP, "models": []}
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            return {"status": "online", "ip": P330_IP, "models": models}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def embed(self, text: str, model: str = EMBEDDING_MODEL) -> Optional[list]:
        """
        Generate a text embedding using the Edge_Node.
        Used for ChromaDB population — saves Gemini API costs.
        """
        if not self.is_online():
            logger.warning("⚠️ Edge_Node offline — falling back to cloud embeddings")
            return None

        try:
            r = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": model, "prompt": text},
                timeout=self.timeout
            )
            if r.status_code == 200:
                return r.json().get("embedding")
            logger.error(f"Edge_Node embedding error: {r.status_code}")
            return None
        except Exception as e:
            logger.error(f"Edge_Node embed failed: {e}")
            return None

    def generate(
        self,
        prompt: str,
        model: str = LIGHT_CHAT_MODEL,
        stream: bool = False
    ) -> Optional[str]:
        """
        Run a lightweight inference task on the Edge_Node.
        Best for: summarization, tagging, classification.
        NOT for: interactive chat (too slow for user-facing tasks).
        """
        if not self.is_online():
            logger.warning("⚠️ Edge_Node offline — task skipped")
            return None

        try:
            r = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=120  # CPU inference is slow — generous timeout
            )
            if r.status_code == 200:
                return r.json().get("response", "").strip()
            return None
        except Exception as e:
            logger.error(f"Edge_Node generate failed: {e}")
            return None

    def summarize(self, text: str) -> Optional[str]:
        """Summarize a block of text using the Edge_Node as background worker."""
        prompt = f"Summarize the following in 3 bullet points:\n\n{text}"
        return self.generate(prompt, model=SUMMARIZER_MODEL)


# Singleton
p330_worker = P330Worker()


if __name__ == "__main__":
    print(f"🖥️  Edge_Node Worker Status: {json.dumps(p330_worker.ping(), indent=2)}")
