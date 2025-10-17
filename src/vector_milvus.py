# src/vectorstore_milvus.py
from typing import List, Dict, Optional
from pymilvus import (
    connections, utility, FieldSchema, CollectionSchema, DataType, Collection
)
from .config import settings
from .embeddings import embed_texts

def connect():
    kwargs = settings.milvus_connect_kwargs()
    # db_name seçimi pymilvus>=2.3 ile connections.connect içinde yapılabiliyor
    connections.connect(alias="default", **kwargs, db_name=settings.milvus_db)

def ensure_collection(dimension: int) -> Collection:
    connect()
    if settings.milvus_collection in utility.list_collections(using="default"):
        c = Collection(settings.milvus_collection)
    else:
        id_f = FieldSchema(
            name=settings.milvus_id_field, dtype=DataType.VARCHAR,
            is_primary=True, max_length=128
        )
        txt_f = FieldSchema(
            name=settings.milvus_text_field, dtype=DataType.VARCHAR,
            max_length=8192
        )
        src_f = FieldSchema(
            name=settings.milvus_source_field, dtype=DataType.VARCHAR,
            max_length=1024
        )
        vec_f = FieldSchema(
            name=settings.milvus_vector_field, dtype=DataType.FLOAT_VECTOR, dim=dimension
        )
        schema = CollectionSchema(
            fields=[id_f, txt_f, src_f, vec_f],
            description="RAG documents for Diyoloji"
        )
        c = Collection(settings.milvus_collection, schema=schema)

    # Index + load
    if not c.indexes:
        c.create_index(
            field_name=settings.milvus_vector_field,
            index_params=settings.milvus_index_params()
        )
    if settings.milvus_partition:
        c.load(partition_names=[settings.milvus_partition])
    else:
        c.load()
    return c

def upsert_texts(items: List[Dict]):
    """
    items: [{"id": "...", "text": "...", "source": "..."}]
    Not: Milvus'ta 'upsert' yok. Duplicate ID engellemek istersen önce delete+insert yapmalısın.
    """
    c = ensure_collection(dimension=settings.milvus_dim)
    ids = [it["id"] for it in items]
    texts = [it["text"] for it in items]
    srcs = [it.get("source","") for it in items]
    vecs = embed_texts(texts)
    c.insert([ids, texts, srcs, vecs])
    c.flush()
    return len(items)

def search(query: str, limit: int = 5, output_fields: Optional[List[str]] = None):
    c = ensure_collection(dimension=settings.milvus_dim)
    qv = embed_texts([query])[0]
    params = settings.milvus_search_params()
    out_fields = output_fields or [settings.milvus_text_field, settings.milvus_id_field, settings.milvus_source_field]
    res = c.search(
        data=[qv],
        anns_field=settings.milvus_vector_field,
        param=params,
        limit=limit,
        output_fields=out_fields,
        expr=None if not settings.milvus_partition else ""  # partition load edildi
    )
    hits = []
    for hit in res[0]:
        item = {
            "distance": hit.distance,
            "id": hit.entity.get(settings.milvus_id_field, ""),
            "text": hit.entity.get(settings.milvus_text_field, ""),
            "source": hit.entity.get(settings.milvus_source_field, ""),
        }
        hits.append(item)
    return hits
