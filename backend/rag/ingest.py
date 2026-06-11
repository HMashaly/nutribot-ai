"""
rag/ingest.py — Incremental embedding pipeline for NutriBot knowledge base.

Run once after cloning, and again whenever you add/edit files in knowledgebase/:
    python rag/ingest.py

Uses MD5 hashing to skip unchanged files (incremental ingest).
"""

import hashlib
import json
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from loguru import logger

_ROOT = Path(__file__).parent.parent
DATA_DIR = _ROOT / "knowledgebase"
CHROMA_DIR = _ROOT / "chroma_db"
COLLECTION_NAME = "nutribot"
HASH_STORE_PATH = CHROMA_DIR / ".file_hashes.json"


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_hashes() -> dict[str, str]:
    if HASH_STORE_PATH.exists():
        return json.loads(HASH_STORE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_hashes(hashes: dict[str, str]) -> None:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    HASH_STORE_PATH.write_text(json.dumps(hashes, indent=2), encoding="utf-8")


def ingest(force: bool = False):
    """
    Embed all markdown files in knowledgebase/ into ChromaDB.
    Only re-embeds files whose MD5 hash has changed since last run.
    Pass force=True to re-embed everything regardless.
    """
    logger.info("Starting ingest from {}", DATA_DIR)
    if not DATA_DIR.exists():
        raise FileNotFoundError(f"Knowledge base folder not found: {DATA_DIR}")

    known_hashes = {} if force else _load_hashes()
    new_hashes: dict[str, str] = {}
    changed_files: list[Path] = []

    all_files = list(DATA_DIR.rglob("*.md")) + list(DATA_DIR.rglob("*.txt"))
    for file_path in all_files:
        file_hash = _md5(file_path)
        key = str(file_path)
        new_hashes[key] = file_hash
        if force or known_hashes.get(key) != file_hash:
            changed_files.append(file_path)

    if not changed_files:
        logger.info("No changed files detected. Skipping ingest.")
        return load_vectorstore()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=80,
        separators=["\n## ", "\n### ", "\n\n", "\n", " "],
    )
    vectorstore = load_vectorstore()

    for file_path in changed_files:
        loader = TextLoader(str(file_path), encoding="utf-8")
        documents = loader.load()
        chunks = splitter.split_documents(documents)
        logger.info("Ingesting {} chunks from {}", len(chunks), file_path.name)
        vectorstore.add_documents(chunks)

    _save_hashes(new_hashes)
    logger.info("Ingest complete. {} file(s) processed.", len(changed_files))
    return vectorstore


def load_vectorstore():
    """Load the persisted ChromaDB vectorstore (must have run ingest first)."""
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
    )
    return Chroma(
        persist_directory=str(CHROMA_DIR),
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME,
    )


if __name__ == "__main__":
    ingest()
