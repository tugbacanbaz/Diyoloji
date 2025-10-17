"""
RAG Pipeline implementation for Diyoloji project.
Handles document processing, vector storage, and query processing.
"""

from __future__ import annotations

# Standard library imports
import os
import re
import html as ihtml
import json
import time
import hashlib
from typing import Dict, List, Tuple, Optional, Iterable
from urllib.parse import urlparse

# Third-party imports
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
from pymilvus import (
    connections,
    Collection,
    utility,
    FieldSchema,
    CollectionSchema,
    DataType
)
from langchain.callbacks.manager import CallbackManagerForChainRun
from langsmith import traceable

# Local imports
from src.config import settings

from src.debug_logger import debug_log
# --- Memory / Retrieval logging flags (ENV üzerinden) ---
MEM_HISTORY_TO_INDEX = str(os.getenv("MEMORY_HISTORY_TO_INDEX", "true")).lower() in ("1","true","yes","on")
MEM_HISTORY_PENALTY = float(os.getenv("MEMORY_HISTORY_PENALTY", "0.05") or 0.0)  # 0..0.5
RETRIEVAL_LOG_PATH = os.getenv("RETRIEVAL_LOG_PATH", "data/retrieval_events.jsonl")


# Initialize environment and LangSmith configuration
def _init_environment():
    """Initialize environment variables and LangSmith configuration."""
    try:
        load_dotenv()
    except Exception as e:
        print(f"Warning: Could not load .env file: {e}")

    # Set up LangSmith environment variables
    if not os.getenv("LANGCHAIN_ENDPOINT") and os.getenv("LANGSMITH_ENDPOINT"):
        os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGSMITH_ENDPOINT")
    if not os.getenv("LANGCHAIN_API_KEY") and os.getenv("LANGSMITH_API_KEY"):
        os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
    if not os.getenv("LANGCHAIN_PROJECT") and os.getenv("LANGSMITH_PROJECT"):
        os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT")

# Initialize environment
_init_environment()

# -------- LangSmith tracing (runtime toggle) --------

try:
    from langsmith import traceable as _traceable
except Exception:
    def _traceable(*a, **k):
        def _wrap(f): return f
        return _wrap

def _getbool(name: str, default="false") -> bool:
    v = os.getenv(name, default)
    return str(v).strip().lower() in ("1", "true", "yes", "on", "1")

def t_any(name: str):
    """
    Yalnızca genel tracing anahtarı açıksa trace yollar.
    Açan bayraklardan herhangi biri yeterli:
      - LANGCHAIN_TRACING_V2=true  veya  LANGSMITH_TRACING=true
    """
    def _dec(fn):
        traced = _traceable(name=name)(fn)
        def _wrapped(*args, **kwargs):
            tracing_on = _getbool("LANGCHAIN_TRACING_V2") or _getbool("LANGSMITH_TRACING")
            return traced(*args, **kwargs) if tracing_on else fn(*args, **kwargs)
        return _wrapped
    return _dec

def t_ingest(name: str):
    """
    Ingestion çağrıları için: hem genel tracing hem ingest bayrağı gerekli.
      - (LANGCHAIN_TRACING_V2=true  veya  LANGSMITH_TRACING=true)
      VE
      - (LANGSMITH_TRACE_INGEST=true  veya  TRACE_INGEST=true)
    """
    def _dec(fn):
        traced = _traceable(name=name)(fn)
        def _wrapped(*args, **kwargs):
            tracing_on = _getbool("LANGCHAIN_TRACING_V2") or _getbool("LANGSMITH_TRACING")
            ingest_on = _getbool("LANGSMITH_TRACE_INGEST") or _getbool("TRACE_INGEST")
            return traced(*args, **kwargs) if (tracing_on and ingest_on) else fn(*args, **kwargs)
        return _wrapped
    return _dec

# --- Milvus URI sanitizer (Serverless uyumluluk) ---
def _sanitize_milvus_uri(uri: str) -> str:
    """
    Zilliz Serverless için:
    - cloud.zilliz.com -> zillizcloud.com
    - :19530 (self-hosted gRPC portu) -> kaldır
    - Şema yoksa https:// ekle
    """
    if not uri:
        return uri
    uri = uri.strip()
    # Yanlış domain düzeltmesi
    uri = uri.replace(".cloud.zilliz.com", ".zillizcloud.com")
    # Self-hosted gRPC portunu kaldır
    if uri.endswith(":19530"):
        uri = uri[:-6]
    # Şema yoksa ekle
    parsed = urlparse(uri)
    if not parsed.scheme:
        uri = "https://" + uri
    return uri

# -------- Constants & Configuration --------
_CLIENT = OpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url or None,
)

# -------- Parametreler --------
_EMBED_BATCH = 64
_TEXT_MAX = 32760
_VALID_TOOLS = {"billing", "roaming", "package", "coverage", "app"}

# ----------------- Yardımcılar -----------------
def _maybe_normalize(v: List[float]) -> List[float]:
    """Milvus metric 'IP' ise cosine eşdeğeri için normalize et; diğerlerinde dokunma."""
    if settings.milvus_metric.upper() == "IP":
        arr = np.array(v, dtype=np.float32)
        n = np.linalg.norm(arr)
        if n > 0:
            arr = arr / n
        return arr.tolist()
    return v

def _hash_row_id(url: str, category: str, chunk_id: int) -> int:
    h = hashlib.md5(f"{url}|{category}|{chunk_id}".encode()).hexdigest()[:16]
    return int(h, 16) % (2**63 - 1)

def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    chunks: List[str] = []
    i = 0
    step = max(chunk_size - overlap, 1)
    L = len(text)
    while i < L:
        chunks.append(text[i : i + chunk_size])
        i += step
    return chunks

def _iter_json_records(path: str) -> Iterable[Dict]:
    """
    Tek .json / .jsonl dosyası veya bu uzantıları içeren bir klasör desteklenir.
    Kayıt şemaları:
      - {"url": str, "category": str?, "content_text"/"content_html"/"text": ..., "chunks"?: [...]}
      - Üst seviye {records|data|items|docs: [...]} kapları da desteklenir.
    """
    def _yield_from_obj(obj):
        if isinstance(obj, dict):
            for key in ("records", "data", "items", "docs"):
                if isinstance(obj.get(key), list):
                    for rec in obj[key]:
                        if isinstance(rec, dict):
                            yield rec
                    return
            yield obj
        elif isinstance(obj, list):
            for rec in obj:
                if isinstance(rec, dict):
                    yield rec

    if os.path.isdir(path):
        for fn in os.listdir(path):
            if fn.lower().endswith((".json", ".jsonl")):
                yield from _iter_json_records(os.path.join(path, fn))
        return

    if path.lower().endswith(".jsonl"):
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                yield from _yield_from_obj(obj)
        return

    with open(path, "r", encoding="utf-8-sig") as f:
        try:
            data = json.load(f)
        except Exception:
            return
    yield from _yield_from_obj(data)

def _extract_chunks_from_record(rec: Dict) -> List[str]:
    """
    Kayıttan metin parçası çıkar.
    Öncelik: chunks -> content_text -> content_html -> diğer text benzeri alanlar.
    """
    if isinstance(rec.get("chunks"), list):
        return [str(c or "") for c in rec["chunks"]]

    title = (rec.get("title") or "").strip()

    if rec.get("content_text"):
        full = (title + "\n" if title else "") + str(rec["content_text"])
        return chunk_text(full, settings.chunk_size, settings.chunk_overlap)

    if rec.get("content_html"):
        html_str = str(rec["content_html"])
        txt = re.sub(r"<[^>]+>", " ", html_str)
        txt = ihtml.unescape(txt)
        txt = " ".join(txt.split())
        full = (title + "\n" if title else "") + txt
        return chunk_text(full, settings.chunk_size, settings.chunk_overlap)

    text_candidates = [
        "text", "content", "body", "page_text", "clean_text",
        "raw_text", "plaintext", "text_content", "textContent",
    ]
    for k in text_candidates:
        if rec.get(k):
            v = rec[k]
            if isinstance(v, list):
                merged = "\n\n".join(str(x or "") for x in v)
            elif isinstance(v, dict):
                merged = str(v.get("text") or v.get("content") or "")
            else:
                merged = str(v)
            full = (title + "\n" if title else "") + merged
            return chunk_text(full, settings.chunk_size, settings.chunk_overlap)

    return []

def _map_category(scraped_cat: Optional[str], slug: Optional[str] = None, title: str = "", breadcrumb: str = "") -> str:
    text = " ".join([scraped_cat or "", slug or "", title or "", breadcrumb or ""]).lower()

    if any(k in text for k in ["fatura", "odeme", "ödeme", "borç", "tahsilat", "kesim"]):
        return "billing"
    if any(k in text for k in ["roaming", "yurtdışı", "yurtdisi", "uluslararası", "abroad"]):
        return "roaming"
    if any(k in text for k in ["kapsama", "çekim", "4.5g", "5g", "şebeke", "coverage", "signal"]):
        return "coverage"
    if any(k in text for k in ["dijital operatör", "uygulama", "app", "giriş", "şifre", "login", "reset"]):
        return "app"
    if any(k in text for k in ["abonelik", "hat", "tarife", "paket", "devir"]):
        return "package"
    return "package"

@t_ingest(name="embed_texts")
def embed_texts(texts: List[str]) -> List[List[float]]:
    vectors: List[List[float]] = []
    if not texts:
        return vectors
    for start in range(0, len(texts), _EMBED_BATCH):
        batch = texts[start : start + _EMBED_BATCH]
        resp = _CLIENT.embeddings.create(model=settings.openai_embed_model, input=batch)
        for d in resp.data:
            vectors.append(_maybe_normalize(d.embedding))
    return vectors

# --- TR lowercase helper (İ/ı sorunlarını önle)
def _tr_lower(s: str) -> str:
    if not s: return ""
    return (s.replace("İ","i").replace("I","ı")).lower()

# --- Runtime kategori router (sorgu için)
def route_category_from_text(text: str) -> Optional[str]:
    t = _tr_lower(text)

    # devir / hat sahibi değişikliği → package
    if any(k in t for k in [
        "hat devri", "hattı devret", "hattimi devret", "üzerine devret",
        "hat sahibi değiş", "sahiplik devri", "numara devri", "isim değişikliği"
    ]):
        return "package"

    # fatura/ödeme → billing
    if any(k in t for k in [
        "fatura", "ödeme", "odeme", "borç", "tahsilat", "kesim", "yüksek geldi", "indirim", "itiraz"
    ]):
        return "billing"

    # yurtdışı → roaming
    if any(k in t for k in ["roaming", "yurtdışı", "yurtdisi", "abroad", "uluslararası"]):
        return "roaming"

    # kapsama/şebeke → coverage
    if any(k in t for k in ["kapsama", "çekim", "cekim", "şebeke", "sebeke", "4.5g", "5g", "coverage", "signal"]):
        return "coverage"

    # uygulama → app
    if any(k in t for k in ["dijital operatör", "dijital operator", "uygulama", "app", "giriş", "sifre", "şifre", "login", "reset"]):
        return "app"

    # default
    return None

# ----------------- Milvus -----------------
def _connect_milvus():
    """
    Connect to Milvus/Zilliz Cloud instance using the configured settings.
    """
    try:
        # Close any existing connections first
        if connections.has_connection("default"):
            connections.remove_connection("default")

        uri = settings.milvus_uri
        token = settings.milvus_token
        db_name = settings.milvus_db

        # Ensure URI has https:// prefix and no trailing port
        clean_uri = uri.rstrip('/')
        if ':19530' in clean_uri:
            clean_uri = clean_uri.replace(':19530', '')
        if not clean_uri.startswith(('http://', 'https://')):
            clean_uri = 'https://' + clean_uri

        print(f"Debug - Connecting to Zilliz Cloud:")
        print(f"URI: {clean_uri}")
        print(f"DB: {db_name}")
        print(f"Token length: {len(token) if token else 0}")

        # Connect using the cleaned URI
        connections.connect(
            alias="default",
            uri=clean_uri,
            token=token,
            db_name=db_name,
            secure=True,
            timeout=30
        )
    except Exception as e:
        print(f"Milvus Connection Error: {str(e)}")
        raise
    
        # Verify connection with health check
        _ = utility.get_server_version()
    except Exception as e:
        print(f"Milvus Connection Error - URI: {uri}, DB: {db_name}")
        print(f"Error Details: {e}")
        raise

def _ensure_collection() -> Collection:
    _connect_milvus()
    name = settings.milvus_collection
    TEXT_F = getattr(settings, "milvus_text_field", "text")
    VEC_F  = getattr(settings, "milvus_vector_field", "embedding")

    if not utility.has_collection(name):
        fields = [
            FieldSchema(name="id",        dtype=DataType.INT64,  is_primary=True, auto_id=False),
            FieldSchema(name="category",  dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="url",       dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="chunk_id",  dtype=DataType.INT64),
            FieldSchema(name=TEXT_F,      dtype=DataType.VARCHAR, max_length=_TEXT_MAX),
            FieldSchema(name=VEC_F,       dtype=DataType.FLOAT_VECTOR, dim=settings.milvus_dim),
        ]
        schema = CollectionSchema(fields, description="Diyoloji Docs")
        col = Collection(name, schema)
    else:
        col = Collection(name)

    # ---- INDEX GUARD: varsa yeniden yaratma
    existing = []
    try:
        existing = col.indexes  # pymilvus 2.6.x
    except Exception:
        existing = []

    if not existing:
        idx_params = settings.milvus_index_params()
        try:
            col.create_index(field_name=VEC_F, index_params=idx_params)
        except Exception as e:
            # 65535: duplicate/distinct index denemesi veya server-side varyasyon
            print(f"[warn] create_index skipped: {e}")

    part = getattr(settings, "milvus_partition", None)
    try:
        col.load(partition_names=[part] if part else None)
    except Exception:
        col.load()

    return col

def _milvus_delete_ids(col: Collection, ids: List[int]) -> None:
    if not ids:
        return
    CHUNK = 2000
    for i in range(0, len(ids), CHUNK):
        sub = ids[i : i + CHUNK]
        expr = f"id in {sub}"
        try:
            col.delete(expr)
        except Exception:
            pass

@t_ingest(name="upsert_docs")
def upsert_docs(
    docs: List[Tuple[str, str, str, int, List[float]]]
) -> int:
    """
    docs: List[(category, url, chunk_text_val, chunk_id, embedding_vec)]
    """
    if not docs:
        return 0

    col = _ensure_collection()

    TEXT_F = getattr(settings, "milvus_text_field", "text")
    VEC_F  = getattr(settings, "milvus_vector_field", "embedding")

    ids, cats, urls, cids, texts, vecs = [], [], [], [], [], []
    for category, url, chunk_text_val, chunk_id, emb in docs:
        rid = _hash_row_id(url, category, chunk_id)
        ids.append(rid)
        cats.append(category or "")
        urls.append(url or "")
        cids.append(int(chunk_id))
        texts.append((chunk_text_val or "")[:_TEXT_MAX])
        vecs.append(emb)

    _milvus_delete_ids(col, ids)

    # Insert sırası schema’daki alan sıranızla eşleşmeli
    col.insert([
        ids,
        cats,
        urls,
        cids,
        texts,   # TEXT_F
        vecs,    # VEC_F
    ])
    col.flush()
    return len(ids)

# ----------------- JSON Ingest -----------------
@t_ingest(name="ingest_from_json")
def ingest_from_json(path: str) -> Dict[str, int]:
    per_cat: Dict[str, int] = {}
    total = 0
    payload_texts: List[Tuple[str, str, str, int]] = []

    for rec in _iter_json_records(path):
        url = (rec.get("url") or "").strip()
        if not url:
            continue

        mapped_cat = _map_category(
            scraped_cat = rec.get("category"),
            slug        = rec.get("subcategory") or rec.get("sub_category"),
            title       = rec.get("title") or "",
            breadcrumb  = rec.get("breadcrumb") or "",
        )

        chunks = _extract_chunks_from_record(rec)
        if not chunks:
            continue

        for i, ch in enumerate(chunks):
            payload_texts.append((mapped_cat, url, ch, i))

    if not payload_texts:
        return {"total_chunks": 0}

    vectors = embed_texts([p[2] for p in payload_texts])
    docs = [
        (cat, url, ch, cid, vectors[i])
        for i, (cat, url, ch, cid) in enumerate(payload_texts)
    ]

    wrote = upsert_docs(docs)
    total += wrote
    for cat, _, _, _, _ in docs:
        per_cat[cat] = per_cat.get(cat, 0) + 1

    return {"total_chunks": total, **per_cat}

def upsert_history_qa(session_id: str, turn_id: int, question: str, answer: str, intent: str = "other") -> int:
    """
    Bir turdaki (soru+cevap) çiftini 'history' kategorisiyle vektör indekse ekler.
    Benzer sorularda recall amaçlı geri çağrılır.
    """
    if not MEM_HISTORY_TO_INDEX:
        return 0
    if not question or not question.strip() or not answer or not answer.strip():
        return 0

    # Metni derle ve embed et
    q = question.strip()[:512]
    a = answer.strip()[:2000]
    text = f"SORU: {q}\nCEVAP: {a}"

    vecs = embed_texts([text])
    if not vecs:
        return 0

    col = _ensure_collection()
    TEXT_F = getattr(settings, "milvus_text_field", "text")
    VEC_F  = getattr(settings, "milvus_vector_field", "embedding")

    # Tekil kimlik: session+turn’dan deterministik int64
    url = f"history://{session_id}#{turn_id}"
    chunk_id = 0
    rid = _hash_row_id(url, "history", chunk_id)

    try:
        _milvus_delete_ids(col, [rid])
        col.insert([
            [rid],               # id
            ["history"],         # category
            [url],               # url
            [chunk_id],          # chunk_id
            [text[:_TEXT_MAX]],  # TEXT_F
            [vecs[0]],           # VEC_F
        ])
        col.flush()
        return 1
    except Exception as e:
        print(f"[MEM] upsert_history_qa failed: {e}")
        return 0

# ----------------- Arama -----------------
@t_any(name="search")
@debug_log(prefix="Search")
def search(query: str, category: Optional[str], top_k: int = 6):
    """
    Hem HNSW hem IVF için doğru arama paramlarını kullanır.
    output_fields ENV’den gelen metin/başlık alanlarıyla eşleşir.
    """
    TEXT_F = getattr(settings, "milvus_text_field", "text")
    VEC_F  = getattr(settings, "milvus_vector_field", "embedding")

    qv = embed_texts([query])[0]
    col = _ensure_collection()

    search_params = settings.milvus_search_params()

    expr = f'category == "{category}"' if category else None

    res = col.search(
        data=[qv],
        anns_field=VEC_F,
        param=search_params,
        limit=top_k,
        expr=expr,
        output_fields=["url", TEXT_F, "category", "chunk_id"],
        consistency_level="Strong",
    )

    hits = []
    for h in res[0]:
        ent = h.entity or {}
        hits.append({
            "url": ent.get("url"),
            "text": ent.get(TEXT_F),
            "category": ent.get("category"),
            "chunk_id": int(ent.get("chunk_id")),
            "score": float(h.distance),
        })
    return hits

# ----------------- CLI -----------------
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Diyoloji - JSON/JSONL ingest & search (content only)")
    ap.add_argument("--file", type=str, help="JSON/JSONL (content_text/content_html/text/chunks)", required=False)
    ap.add_argument("--query", type=str, help="Hızlı arama sorgusu (test için)", required=False)
    ap.add_argument("--category", type=str, help="Arama kategorisi (billing/roaming/package/coverage/app)", required=False)
    ap.add_argument("--check-milvus", action="store_true", help="Koleksiyonda kaç kayıt var, örnek satırları göster")
    args = ap.parse_args()

    # 1) İçerik ingestion
    if args.file:
        stats = ingest_from_json(args.file)
        print("[INGEST CONTENT DONE]" if stats.get("total_chunks", 0) > 0 else "[NO CONTENT FOUND]", stats)

    # 2) Hızlı arama
    if args.query:
        out = search(args.query, category=args.category, top_k=settings.max_context_docs)
        for i, h in enumerate(out, 1):
            print(f"[{i}] {h['score']:.4f} | {h['category']} | {h['url']}\n{h['text'][:220]}\n")

    # 3) Milvus kontrol
    if args.check_milvus:
        col = _ensure_collection()
        print("num_entities:", col.num_entities)
        rows = col.query(
            expr="chunk_id >= 0",
            output_fields=["url", "category", "chunk_id"],
            limit=10,
        )
        for r in rows:
            print(r)
