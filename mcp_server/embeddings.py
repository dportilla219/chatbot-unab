"""Embeddings locales multilingües (384 dimensiones), sin API key.

Modelo por defecto: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 vía fastembed (ONNX, CPU).
EMBED_BACKEND=hash usa un embedding determinista de respaldo (solo para pruebas sin internet).
"""
import hashlib
import math
import os
import re

DIM = 384
MODEL_NAME = os.getenv("EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
BACKEND = os.getenv("EMBED_BACKEND", "fastembed")

_model = None


def _hash_embed(text: str) -> list[float]:
    v = [0.0] * DIM
    tokens = re.findall(r"\w+", text.lower())
    for tok in tokens:
        for gram in {tok, *(tok[i:i + 4] for i in range(max(1, len(tok) - 3)))}:
            h = int(hashlib.md5(gram.encode()).hexdigest(), 16)
            v[h % DIM] += 1.0 if (h >> 8) & 1 else -1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def embed(texts: list[str]) -> list[list[float]]:
    global _model
    if BACKEND == "hash":
        return [_hash_embed(t) for t in texts]
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(MODEL_NAME, cache_dir=os.getenv("EMBED_CACHE", "/models"))
    return [list(map(float, v)) for v in _model.embed(texts, batch_size=16)]


def to_pgvector(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"
