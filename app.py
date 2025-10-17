from fastapi import FastAPI, UploadFile, File
from starlette.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance
import uuid
import os
# Use package-relative imports. Run the server from the project root with:
#   python -m uvicorn server.app:app
from .config import QDRANT_URL, QDRANT_API_KEY, COLLECTION_NAME, CHUNK_SIZE, TOP_K, HF_API_KEY, HF_EMBEDDING_MODEL
from .utils import extract_text, chunk_text, get_embedding, llm_answer, ollama_health_check

app = FastAPI()

# Serve frontend folder (corrected path)
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/frontend", StaticFiles(directory=frontend_path), name="frontend")

# Qdrant client (initialize safely; if init fails we keep client=None and
# provide clearer error messages on endpoints)
client = None
try:
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    # Ensure collection exists (best-effort)
    try:
        vector_dim = 384  # MiniLM-L6-v2
        existing = [col.name for col in client.get_collections().collections]
        if COLLECTION_NAME not in existing:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE),
            )
    except Exception as e:
        print(f"[startup] Warning: couldn't ensure collection exists: {e}")
except Exception as e:
    print(f"[startup] Warning: Qdrant client initialization failed: {e}")
    client = None



@app.on_event("startup")
async def startup_checks():
    """Run simple startup checks and print helpful messages for missing config or deps."""
    # check values from config module first, then env vars
    from . import config as _cfg
    missing = []
    for var in ("QDRANT_URL", "QDRANT_API_KEY", "HF_API_KEY"):
        val = getattr(_cfg, var, None) or os.getenv(var)
        if not val:
            missing.append(var)
    if missing:
        print(f"[startup] WARNING: missing environment variables: {missing}")

    # Check optional packages
    try:
        import sentence_transformers  # type: ignore
    except Exception:
        print("[startup] NOTE: 'sentence-transformers' not available; embedding endpoints will fail until installed.")

    if client is None:
        print("[startup] NOTE: Qdrant client is not connected; upload and query endpoints will return errors until connection is fixed.")
    # Check Ollama availability and report it
    try:
        ok = ollama_health_check()
        if not ok:
            print(f"[startup] NOTE: Ollama (or configured LLM) at {os.getenv('OLLAMA_API_URL')} did not respond to health check.")
    except Exception:
        pass

@app.get("/health")
async def health():
    """Simple health endpoint returning status of key subsystems."""
    qdrant_ok = client is not None
    ollama_ok = ollama_health_check()
    status = {
        "qdrant": "connected" if qdrant_ok else "disconnected",
        "ollama": "available" if ollama_ok else "unavailable",
    }
    return status

# Upload endpoint
@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    text = extract_text(file)
    if not text:
        return {"status": "error", "message": "Failed to extract text"}

    chunks = chunk_text(text, CHUNK_SIZE)
    points = []
    for chunk in chunks:
        vector = get_embedding(chunk)
        if vector:
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={"filename": file.filename, "text": chunk}
            )
            points.append(point)

    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points)
        return {"status": "success", "chunks_uploaded": len(points)}
    else:
        return {"status": "error", "message": "Failed to generate embeddings"}

# Query endpoint
@app.post("/query")
async def query_document(query: dict):
    question = query.get("question")
    if not question:
        return {"error": "Question is required"}

    vector = get_embedding(question)
    if not vector:
        return {"error": "Failed to generate query embedding"}

    search_result = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        limit=TOP_K
    )

    # Get top chunks
    top_chunks = [{"filename": hit.payload.get("filename"), "text": hit.payload.get("text")} for hit in search_result]

    # Get final answer from LLM
    answer = llm_answer(question, top_chunks)
    return {"answer": answer, "sources": top_chunks}

# Serve main page
@app.get("/", response_class=HTMLResponse)
async def get_frontend():
    index_file = os.path.join(frontend_path, "index.html")
    with open(index_file, "r", encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    # Allow running this file directly for convenience in development:
    #   cd server
    #   python app.py
    # This will start uvicorn programmatically.
    try:
        import uvicorn

        uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
    except Exception as e:
        print("Failed to start server via uvicorn:", e)
