import re
from typing import List, Optional

import requests

from .config import HF_EMBEDDING_MODEL, OLLAMA_API_URL, LLM_MODEL


# Lazy-loaded embedding model (sentence-transformers)
_embedding_model = None


def _load_embedding_model():
    """Lazily load the sentence-transformers model.

    Returns None if the library or model can't be loaded.
    """
    global _embedding_model
    if _embedding_model is None:
        try:
            import importlib

            module = importlib.import_module("sentence_transformers")
            SentenceTransformer = getattr(module, "SentenceTransformer")

            _embedding_model = SentenceTransformer(HF_EMBEDDING_MODEL)
        except Exception as e:
            print(f"Failed to load embedding model ({HF_EMBEDDING_MODEL}): {e}")
            _embedding_model = None
    return _embedding_model


def extract_text(file) -> Optional[str]:
    """Extract text from PDF or TXT files.

    Uses PyPDF2 for PDFs and reads bytes for .txt files.
    """
    filename = getattr(file, "filename", "").lower()
    try:
        if filename.endswith(".pdf"):
            try:
                from PyPDF2 import PdfReader

                reader = PdfReader(file.file)
                pages = []
                for p in reader.pages:
                    text = p.extract_text()
                    if text:
                        pages.append(text)
                return "\n".join(pages).strip()
            except Exception as e:
                print(f"PDF extraction failed (PyPDF2): {e}")
                return None
        elif filename.endswith(".txt"):
            try:
                data = file.file.read()
                if isinstance(data, bytes):
                    return data.decode("utf-8", errors="ignore").strip()
                return str(data).strip()
            except Exception as e:
                print(f"Text file read failed: {e}")
                return None
        else:
            return None
    except Exception as e:
        print(f"Text extraction failed: {e}")
        return None


def chunk_text(text: str, chunk_size: int = 500) -> List[str]:
    """Split text into chunks of ~chunk_size words."""
    if not text:
        return []
    words = re.split(r"\s+", text)
    return [" ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)]


def get_embedding(text: str) -> Optional[List[float]]:
    """Return embedding vector for text using sentence-transformers or None."""
    model = _load_embedding_model()
    if model is None:
        print("Embedding model not available. Install 'sentence-transformers' and ensure model is accessible.")
        return None
    try:
        vector = model.encode(text)
        return vector.tolist() if hasattr(vector, "tolist") else list(vector)
    except Exception as e:
        print(f"Embedding generation failed: {e}")
        return None


def llm_answer(question: str, top_chunks: List[dict]) -> str:
    """Send a completion request to Ollama and return the text answer."""
    context_text = "\n\n".join([c.get("text", "") for c in top_chunks])
    prompt = f"Answer the question based on the following context:\n{context_text}\n\nQuestion: {question}\nAnswer:"
    try:
        resp = requests.post(
            f"{OLLAMA_API_URL}/v1/completions",
            json={"model": LLM_MODEL, "prompt": prompt, "max_tokens": 512},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if "completion" in data:
            return data["completion"]
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0].get("text", "")
        return "No answer generated."
    except Exception as e:
        # Provide a user-friendly fallback when the LLM endpoint is unreachable.
        msg = str(e)
        # Common connection errors from requests
        connection_errors = ["Connection refused", "Failed to establish a new connection", "Max retries exceeded"]
        if any(tok in msg for tok in connection_errors):
            # Log the exception for server-side debugging and return an actionable message to the client
            print(f"[llm] Error contacting LLM at {OLLAMA_API_URL}: {e}")
            return (
                "LLM backend not available. The server attempted to contact the configured LLM at "
                f"{OLLAMA_API_URL} but couldn't connect."
                "\nActions you can take:"
                "\n - Run Ollama locally (https://ollama.ai) or start your LLM service and ensure it listens on the configured URL."
                "\n - Set the environment variable OLLAMA_API_URL to a reachable endpoint (for Docker on Windows use http://host.docker.internal:11434)."
                "\n - Or configure the application to use a hosted LLM API and update the code to call that API instead."
            )
        # Fallback: include the exception text for other error types
        print(f"[llm] LLM request failed: {e}")
        return f"LLM request failed: {e}"


def ollama_health_check(timeout: int = 5) -> bool:
    """Return True if the configured Ollama endpoint responds to a simple GET/health check.

    This is a lightweight helper used by app startup or a /health endpoint.
    """
    try:
        resp = requests.get(f"{OLLAMA_API_URL}/health", timeout=timeout)
        return resp.status_code == 200
    except Exception as e:
        print(f"[health] Ollama health check failed for {OLLAMA_API_URL}: {e}")
        return False
