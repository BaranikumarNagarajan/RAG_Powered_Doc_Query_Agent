import os


# NOTE: It's safer to provide credentials and URLs via environment variables
# when running in Docker or production. These values fall back to the
# current literals for local development, but you should set the corresponding
# environment variables (or mount a secrets file) when deploying.

# Qdrant
QDRANT_URL = os.getenv(
	"QDRANT_URL",
	"https://8df6794d-55d2-44b4-a98e-5281e6c13079.us-west-2-0.aws.cloud.qdrant.io:6333",
)
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "documents")

# Chunking/search
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
TOP_K = int(os.getenv("TOP_K", "3"))

# Ollama
# NOTE: When running inside Docker on Windows/macOS, you may want to set
# OLLAMA_API_URL to http://host.docker.internal:11434 so containers can reach
# a service running on the host machine. For simple local development keep
# the default as host.docker.internal which works when docker-compose wires
# the value for you (see docker-compose.yml).
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://host.docker.internal:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "gemma3:270m")

# Hugging Face
HF_API_KEY = os.getenv("HF_API_KEY", "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")
HF_EMBEDDING_MODEL = os.getenv("HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


def _warn_if_hardcoded():
	"""Print a small runtime warning if sensitive keys are still hard-coded.

	This is helpful during development but optional. The function is not
	automatically invoked to avoid noisy logs; call it from app startup if you
	want an explicit check.
	"""
	hardcoded = []
	if HF_API_KEY:
		# Best-effort detection of example HF keys that start with 'hf_'
		if HF_API_KEY.startswith("hf_"):
			hardcoded.append("HF_API_KEY")
		else:
			# If the env var was provided but the value looks like a placeholder,
			# still warn so users can double-check.
			if HF_API_KEY.lower().startswith("replace") or "your_hf_key" in HF_API_KEY:
				hardcoded.append("HF_API_KEY")
	if QDRANT_API_KEY:
		hardcoded.append("QDRANT_API_KEY")
	if hardcoded:
		msg = (
			"Potentially hard-coded config detected: {}.\n"
			"Consider setting these via environment variables or Docker secrets."
		).format(", ".join(hardcoded))
		try:
			# Avoid importing logging at module import time; print is fine here.
			print("[config] WARNING: " + msg)
		except Exception:
			pass

