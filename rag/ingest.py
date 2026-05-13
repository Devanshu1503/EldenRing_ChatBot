"""
Reads all raw data sources, chunks them, embeds with sentence-transformers,
and stores in a local Chroma vector database.

Run once (after all scrapers): python rag/ingest.py
"""

import json
import pdfplumber
import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer

CHROMA_DIR = Path("rag/chroma_db")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

DATA_FILES = {
    "convergence": Path("data/raw/convergence.json"),
    "fextralife":  Path("data/raw/fextralife.json"),
    "fanapi":      Path("data/raw/fanapi.json"),
}
SUMMARIES_FILE = Path("data/raw/summaries.json")
PDF_FILE = Path("data/pdf/quests.pdf")


# ── chunking ──────────────────────────────────────────────────────────────────

def chunk_text(text: str, source: str, title: str = "") -> list[dict]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + CHUNK_SIZE])
        chunks.append({"text": chunk, "source": source, "title": title})
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


# ── loaders ───────────────────────────────────────────────────────────────────

def load_scraped(path: Path, source_name: str) -> list[dict]:
    if not path.exists():
        print(f"  MISSING {path} — skipping")
        return []
    pages = json.loads(path.read_text(encoding="utf-8"))
    chunks = []
    for page in pages:
        chunks.extend(chunk_text(page["text"], source_name, page.get("title", "")))
    return chunks


def load_fanapi(path: Path) -> list[dict]:
    if not path.exists():
        print(f"  MISSING {path} — skipping")
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    chunks = []
    for category, records in data.items():
        for rec in records:
            parts = [f"[{category.upper()}] {rec.get('name', '')}"]
            for key in ("description", "location", "region", "role", "quote", "drops", "effect"):
                val = rec.get(key)
                if val:
                    if isinstance(val, list):
                        val = ", ".join(str(v) for v in val)
                    parts.append(f"{key}: {val}")
            text = " | ".join(parts)
            chunks.append({"text": text, "source": "fanapi", "title": rec.get("name", "")})
    return chunks


def load_summaries(path: Path) -> list[dict]:
    if not path.exists():
        print(f"  MISSING {path} — skipping")
        return []
    summaries = json.loads(path.read_text(encoding="utf-8"))
    # summaries are already pre-chunked, just pass them through
    return [{"text": s["text"], "source": s["source"], "title": s["title"]}
            for s in summaries]


def load_pdf(path: Path) -> list[dict]:
    if not path.exists():
        print(f"  MISSING {path} — skipping")
        return []
    chunks = []
    with pdfplumber.open(path) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    chunks.extend(chunk_text(full_text, "quest_pdf", "All Elden Ring Side Quests In Order"))
    return chunks


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading data ...")
    all_chunks: list[dict] = []
    all_chunks.extend(load_scraped(DATA_FILES["convergence"], "convergence"))
    all_chunks.extend(load_scraped(DATA_FILES["fextralife"],  "fextralife"))
    all_chunks.extend(load_fanapi(DATA_FILES["fanapi"]))
    all_chunks.extend(load_pdf(PDF_FILE))
    all_chunks.extend(load_summaries(SUMMARIES_FILE))

    print(f"Total chunks: {len(all_chunks)}")

    print("Embedding ...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    texts = [c["text"] for c in all_chunks]
    embeddings = model.encode(texts, batch_size=64, show_progress_bar=True)

    print("Storing in Chroma ...")
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # clear existing collection so re-runs are idempotent
    try:
        client.delete_collection("eldenring")
    except Exception:
        pass
    collection = client.create_collection("eldenring")

    batch_size = 500
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i : i + batch_size]
        collection.add(
            ids=[str(i + j) for j in range(len(batch))],
            embeddings=embeddings[i : i + batch_size].tolist(),
            documents=[c["text"] for c in batch],
            metadatas=[{"source": c["source"], "title": c["title"]} for c in batch],
        )
        print(f"  Stored {min(i + batch_size, len(all_chunks))}/{len(all_chunks)}")

    print(f"\nDone. {len(all_chunks)} chunks in Chroma at {CHROMA_DIR}")


if __name__ == "__main__":
    main()
