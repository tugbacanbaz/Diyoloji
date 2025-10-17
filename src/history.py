from __future__ import annotations

import os
import time
import json
import sqlite3
from typing import List, Dict, Optional

from .config import settings

# ---- Config ----
_ENABLED: bool = bool(getattr(settings, "history_enabled", True))
_DB_PATH: str = os.path.abspath(getattr(settings, "history_db", "./diyoloji_history.sqlite"))
_TTL_DAYS: int = int(getattr(settings, "session_ttl_days", 7))

# ---- Internal helpers ----
def _connect() -> sqlite3.Connection:
    # check_same_thread=False → FastAPI altında da rahat kullan
    return sqlite3.connect(_DB_PATH, check_same_thread=False)

def _ensure_db() -> None:
    """DB yoksa oluştur, tablo/indeksleri kur."""
    os.makedirs(os.path.dirname(_DB_PATH) or ".", exist_ok=True)
    with _connect() as cx:
        cx.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user','assistant')),
            content TEXT NOT NULL,
            intent TEXT,
            sentiment TEXT,
            tool TEXT,
            citations TEXT,      -- JSON list[str] (assistant tarafında)
            created_at INTEGER NOT NULL
        )
        """)
        cx.execute("CREATE INDEX IF NOT EXISTS ix_messages_session ON messages(session_id, created_at)")
        cx.commit()

def init_db() -> None:
    """Dışarıdan açıkça çağırmak için."""
    if _ENABLED:
        _ensure_db()

def db_path() -> str:
    return _DB_PATH

# ---- Public API ----
def add_user_message(session_id: str, content: str,
                     intent: Optional[str] = None,
                     sentiment: Optional[str] = None) -> int:
    """Kullanıcı mesajını kaydet."""
    if not _ENABLED:
        return 0
    _ensure_db()
    now = int(time.time())
    with _connect() as cx:
        cur = cx.execute(
            "INSERT INTO messages(session_id, role, content, intent, sentiment, tool, citations, created_at) "
            "VALUES (?, 'user', ?, ?, ?, NULL, NULL, ?)",
            (session_id, content, intent, sentiment, now),
        )
        cx.commit()
        return int(cur.lastrowid)

def add_assistant_message(session_id: str, content: str,
                          tool: Optional[str] = None,
                          intent: Optional[str] = None,
                          sentiment: Optional[str] = None,
                          citations: Optional[List[str]] = None) -> int:
    """Asistan yanıtını kaydet (varsa kaynak linkleri JSON olarak)."""
    if not _ENABLED:
        return 0
    _ensure_db()
    now = int(time.time())
    cit_json = json.dumps(citations or [], ensure_ascii=False)
    with _connect() as cx:
        cur = cx.execute(
            "INSERT INTO messages(session_id, role, content, intent, sentiment, tool, citations, created_at) "
            "VALUES (?, 'assistant', ?, ?, ?, ?, ?, ?)",
            (session_id, content, intent, sentiment, tool, cit_json, now),
        )
        cx.commit()
        return int(cur.lastrowid)

def get_last_turns(session_id: str, limit_msgs: int = 12) -> List[Dict]:
    """
    Son mesajları (user+assistant karışık) döner.
    RAG prompt’una kısa özet gibi eklemek için uygundur.
    """
    if not _ENABLED:
        return []
    _ensure_db()
    with _connect() as cx:
        rows = cx.execute(
            "SELECT role, content, intent, sentiment, tool, citations, created_at "
            "FROM messages WHERE session_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (session_id, int(limit_msgs)),
        ).fetchall()
    # Tersine al → kronolojik sıraya koy
    rows = list(reversed(rows))
    out: List[Dict] = []
    for role, content, intent, sentiment, tool, citations, ts in rows:
        try:
            cit = json.loads(citations) if citations else []
        except Exception:
            cit = []
        out.append({
            "role": role,
            "content": content,
            "intent": intent,
            "sentiment": sentiment,
            "tool": tool,
            "citations": cit,
            "created_at": int(ts),
        })
    return out

def clear_session(session_id: str) -> int:
    """Belirli oturumun tüm mesajlarını sil."""
    if not _ENABLED:
        return 0
    _ensure_db()
    with _connect() as cx:
        cur = cx.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cx.commit()
        return int(cur.rowcount)

def purge_old(ttl_days: Optional[int] = None) -> int:
    """
    TTL geçmişli temizlik. Varsayılan: settings.session_ttl_days (7).
    Basit yaklaşım: cutoff'tan eski tüm mesajları siler.
    """
    if not _ENABLED:
        return 0
    _ensure_db()
    days = int(_TTL_DAYS if ttl_days is None else ttl_days)
    cutoff = int(time.time()) - days * 86400
    with _connect() as cx:
        cur = cx.execute("DELETE FROM messages WHERE created_at < ?", (cutoff,))
        cx.commit()
        return int(cur.rowcount)
