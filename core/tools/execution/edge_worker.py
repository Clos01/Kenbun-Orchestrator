"""
ComputeNode SFF Worker Node Client
============================
Dispatches CPU-bound AI tasks (embeddings, summarization, light inference)
to the Lenovo Low-Wattage Edge Node running Ollama.

The ComputeNode is our "Embeddings Specialist":
  - 32GB RAM: Can run 7B quantized models CPU-only
  - 2GB VRAM: NOT used for GPU inference (too small)
  - Role: Background tasks, embeddings, ChromaDB population

Usage:
    from tools.execution.compute_node_worker import compute_node_worker
    if compute_node_worker.is_online():
        embedding = compute_node_worker.embed("text to embed")
"""
import json
import logging
import requests
from typing import Optional
from tools.infrastructure.config import settings

logger = logging.getLogger(__name__)

ComputeNode_IP = settings.workers.compute_node_ip
ComputeNode_OLLAMA_PORT = settings.workers.compute_node_ollama_port
ComputeNode_BASE_URL = f"http://{ComputeNode_IP}:{ComputeNode_OLLAMA_PORT}"

# Best models for ComputeNode's 32GB RAM + CPU-only profile
EMBEDDING_MODEL = "nomic-embed-text"   # ~274MB — ultra-fast embeddings
LIGHT_CHAT_MODEL = "phi3:mini"         # 3.8B — fast on 32GB RAM at ~5 tok/s
SUMMARIZER_MODEL = "qwen2.5:7b"        # 7B quant — good summaries, ~3 tok/s


class ComputeNodeWorker:
    """
    Lightweight task dispatcher for the ComputeNode CPU inference node.
    All tasks are fire-and-forget background jobs.
    Falls back gracefully if ComputeNode is offline.
    """

    def __init__(self, timeout: int = 10):
        self.base_url = ComputeNode_BASE_URL
        self.timeout = timeout

    def is_online(self) -> bool:
        """Ping the ComputeNode Ollama instance to check availability."""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def ping(self) -> dict:
        """Full health check — returns status and available models."""
        if not self.is_online():
            return {"status": "offline", "ip": ComputeNode_IP, "models": []}
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            return {"status": "online", "ip": ComputeNode_IP, "models": models}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def embed(self, text: str, model: str = EMBEDDING_MODEL) -> Optional[list]:
        """
        Generate a text embedding using the ComputeNode.
        Used for ChromaDB population — saves Gemini API costs.
        """
        if not self.is_online():
            logger.warning("⚠️ ComputeNode offline — falling back to cloud embeddings")
            return None

        try:
            r = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": model, "prompt": text},
                timeout=self.timeout
            )
            if r.status_code == 200:
                return r.json().get("embedding")
            logger.error(f"ComputeNode embedding error: {r.status_code}")
            return None
        except Exception as e:
            logger.error(f"ComputeNode embed failed: {e}")
            return None

    def generate(
        self,
        prompt: str,
        model: str = LIGHT_CHAT_MODEL,
        stream: bool = False
    ) -> Optional[str]:
        """
        Run a lightweight inference task on the ComputeNode.
        Best for: summarization, tagging, classification.
        NOT for: interactive chat (too slow for user-facing tasks).
        """
        if not self.is_online():
            logger.warning("⚠️ ComputeNode offline — task skipped")
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
            logger.error(f"ComputeNode generate failed: {e}")
            return None

    def summarize(self, text: str) -> Optional[str]:
        """Summarize a block of text using the ComputeNode as background worker."""
        prompt = f"Summarize the following in 3 bullet points:\n\n{text}"
        return self.generate(prompt, model=SUMMARIZER_MODEL)


# Singleton
compute_node_worker = ComputeNodeWorker()


if __name__ == "__main__":
    print(f"🖥️  ComputeNode Worker Status: {json.dumps(compute_node_worker.ping(), indent=2)}")
