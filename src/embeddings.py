from typing import List
from openai import OpenAI
from .config import settings

_client = OpenAI(**settings.openai_client_kwargs())

def embed_texts(texts: List[str]) -> List[List[float]]:
    # OpenAI: toplu embedding
    resp = _client.embeddings.create(
        model=settings.openai_embed_model,
        input=[t if isinstance(t, str) else str(t) for t in texts]
    )
    return [d.embedding for d in resp.data]

def embed_query(text: str) -> List[float]:
    return embed_texts([text])[0]