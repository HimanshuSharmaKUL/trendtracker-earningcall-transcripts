from functools import lru_cache

import torch
from sentence_transformers import SentenceTransformer

from backend.config.config import get_settings


def _resolve_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    settings = get_settings()
    return SentenceTransformer(settings.EMBEDDING_MODEL, device=_resolve_device())


@lru_cache(maxsize=1)
def get_semantic_model() -> SentenceTransformer:
    return SentenceTransformer("all-MiniLM-L6-v2", device=_resolve_device())
