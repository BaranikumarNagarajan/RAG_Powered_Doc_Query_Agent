# server/embeddings.py

import requests
from config import HF_API_KEY, HF_EMBEDDING_MODEL

class HuggingFaceEmbedder:
    """Generate embeddings using Hugging Face API."""
    
    def get_embedding(self, text: str):
        headers = {
            "Authorization": f"Bearer {HF_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {"inputs": text}
        response = requests.post(
            f"https://api-inference.huggingface.co/pipeline/feature-extraction/{HF_EMBEDDING_MODEL}",
            headers=headers,
            json=payload
        )
        if response.status_code == 200:
            token_embeddings = response.json()
            # average token embeddings to get single vector
            if isinstance(token_embeddings[0][0], list):
                vector = [sum(x)/len(x) for x in zip(*token_embeddings[0])]
                return vector
            else:
                return token_embeddings[0]
        else:
            raise Exception(f"Hugging Face API error: {response.text}")


class Gemma3Embedder:
    """Dummy Gemma3 embedder. Replace with actual Gemma3 integration."""
    
    def embed(self, content: bytes):
        # Return a fixed-size zero vector (stub)
        return [0.0] * 768
