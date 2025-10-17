from __future__ import annotations

import os
try:
    from dotenv import load_dotenv  # pip install python-dotenv
    load_dotenv()
except Exception:
    pass

# LangSmith env'lerini LangChain eşdeğerlerine taşımak (eksikse)
if not os.getenv("LANGCHAIN_ENDPOINT") and os.getenv("LANGSMITH_ENDPOINT"):
    os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGSMITH_ENDPOINT")
if not os.getenv("LANGCHAIN_API_KEY") and os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
if not os.getenv("LANGCHAIN_PROJECT") and os.getenv("LANGSMITH_PROJECT"):
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT")

# LangSmith trace decorator
try:
    from langsmith import traceable as ls_traceable 
except Exception: 
    def ls_traceable(*a, **k):
        def _wrap(f): return f
        return _wrap

import argparse
from uuid import uuid4
from typing import Optional

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

from .rag import ask as rag_ask
from . import history as hist
from .project_pipeline import ingest_from_json
from .config import settings

from .config import settings as _cfg
from . import history as hist
if getattr(_cfg, "history_enabled", True):
    hist.init_db()

app = FastAPI(title="Diyoloji API")

# Yerel/önyüz denemeleri için CORS (prod'da domain kısıtla)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: üretimde sınırlayın
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatReq(BaseModel):
    text: str
    session_id: Optional[str] = None
    force_tool: Optional[str] = None  # "billing|roaming|package|coverage|app"

@ls_traceable(name="server.chat")
@app.post("/chat")
def chat(req: ChatReq):
    """RAG yanıtı döner (tam içerikle)."""
    import traceback
    try:
        print(f"Processing request: {req.text}")  # Debug log
        
        # Check if OpenAI API key is valid
        if not settings.openai_api_key or len(settings.openai_api_key) < 20:
            raise ValueError("OpenAI API key is not properly configured")
            
        # Initialize OpenAI client
        try:
            _client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url or None,
            )
            # Test the connection
            _client.models.list()
        except Exception as e:
            print(f"OpenAI connection error: {str(e)}")
            raise ValueError("Could not connect to OpenAI API")
            
        out = rag_ask(req.text, force_tool=req.force_tool, session_id=req.session_id)
        print(f"Got response: {out}")  # Debug log
        return {
            "session_id": req.session_id,
            "answer": out.answer,
            "citations": out.citations,
            "tool": out.tool,
            "intent": out.intent,
            "sentiment": out.sentiment,
        }
    except ValueError as ve:
        error_trace = traceback.format_exc()
        print(f"Configuration error: {str(ve)}\n{error_trace}")
        return {
            "session_id": req.session_id,
            "answer": f"Yapılandırma hatası: {str(ve)}",
            "citations": [],
            "tool": "other",
            "intent": "other",
            "sentiment": "neutral",
        }
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Error processing request: {str(e)}\n{error_trace}")
        return {
            "session_id": req.session_id,
            "answer": "Üzgünüm, şu anda bir teknik sorun yaşıyoruz. Lütfen biraz sonra tekrar deneyin.",
            "citations": [],
            "tool": "other",
            "intent": "other",
            "sentiment": "neutral",
            "error": str(e)
        }

# Web UI
@app.get("/")
def ui():
    html = """
    <!doctype html>
    <meta charset="utf-8" />
    <title>Diyoloji Chat</title>
    <style>
      body { font: 16px/1.4 system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 20px; background:#0b1220; color:#e5e7eb}
      .wrap { max-width: 820px; margin: 0 auto; }
      .chat { border: 1px solid #1f2937; border-radius: 12px; padding: 16px; background:#0f172a; height: 60vh; overflow:auto }
      .msg { padding: 10px 12px; margin: 8px 0; border-radius: 10px; white-space: pre-wrap; }
      .u { background:#1f2937; }
      .a { background:#111827; }
      input, button { font: inherit; }
      form { display: flex; gap: 8px; margin-top: 12px; }
      input[type=text] { flex: 1; padding: 10px 12px; border-radius: 10px; border: 1px solid #374151; background:#0b1220; color:#e5e7eb }
      button { padding: 10px 14px; border-radius: 10px; border: 1px solid #374151; background:#111827; color:#e5e7eb; cursor:pointer }
      .hint { color:#9ca3af; font-size: 13px; margin-top: 8px; }
      .meta { color:#9ca3af; font-size:12px; margin-top:4px }
      .cits { font-size:12px; margin-top:6px; color:#9ca3af}
      .cits a { color:#93c5fd; text-decoration:none }
    </style>
    <div class="wrap">
      <h1>Diyoloji</h1>
      <div id="chat" class="chat"></div>
      <form id="f">
        <input id="q" type="text" placeholder="Sorunu yaz ve Enter’a bas" autocomplete="off" />
        <button>Gönder</button>
      </form>
      <div class="hint">Oturum korunur. Aynı sekmede yazışmaya devam edebilirsin.</div>
    </div>
    <script>
      const KEY = "diyoloji_sid";
      let sid = localStorage.getItem(KEY);
      if (!sid) { sid = crypto.randomUUID(); localStorage.setItem(KEY, sid); }

      const chat = document.getElementById("chat");
      const form = document.getElementById("f");
      const q = document.getElementById("q");

      function add(role, text, meta) {
        const div = document.createElement("div");
        div.className = "msg " + (role === "user" ? "u" : "a");
        div.textContent = text;
        if (meta) {
          const m = document.createElement("div");
          m.className = "meta";
          m.textContent = meta;
          div.appendChild(m);
        }
        chat.appendChild(div);
        chat.scrollTop = chat.scrollHeight;
        return div;
      }

      function addCitations(parent, cits) {
        if (!cits || !cits.length) return;
        const d = document.createElement("div");
        d.className = "cits";
        d.innerHTML = "Kaynaklar: " + cits.map(u => `<a href="${u}" target="_blank" rel="noopener">link</a>`).join(" · ");
        parent.appendChild(d);
      }

      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const text = q.value.trim();
        if (!text) return;
        add("user", text);
        q.value = "";

        try {
          const res = await fetch("/chat", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ text, session_id: sid })
          });
          const data = await res.json();
          const meta = `(tool=${data.tool} | intent=${data.intent} | sentiment=${data.sentiment})`;
          const node = add("assistant", data.answer || "(boş yanıt)", meta);
          addCitations(node, data.citations || []);
        } catch (err) {
          add("assistant", "Hata: " + err);
        }
      });
    </script>
    """
    return Response(content=html, media_type="text/html")


# CLI 

def _cmd_ingest(args: argparse.Namespace) -> int:
    if not args.file:
        print("Hata: --file gerekli (JSON/JSONL).")
        return 2
    stats = ingest_from_json(args.file)
    print("Ingest tamam:", stats)
    return 0

def _cmd_ask(args: argparse.Namespace) -> int:
    sid: str = args.session or str(uuid4())
    out = rag_ask(args.query, force_tool=args.tool, session_id=sid)
    if args.json:
        import json as _json
        print(_json.dumps({
            "session_id": sid,
            "answer": out.answer,
            "citations": out.citations,
            "tool": out.tool,
            "intent": out.intent,
            "sentiment": out.sentiment,
        }, ensure_ascii=False, indent=2))
    else:
        print("\nCEVAP:\n", out.answer)
        print("\nKAYNAKLAR:", *out.citations, sep="\n - ")
        print(f"\n(tool={out.tool} | intent={out.intent} | sentiment={out.sentiment} | session_id={sid})")
    return 0

def _cmd_history(args: argparse.Namespace) -> int:
    sid: Optional[str] = args.session
    if not sid:
        print("Hata: --session parametresi gerekli.")
        return 2

    if args.clear:
        deleted = hist.clear_session(sid)
        print(f"Silinen kayıt sayısı: {deleted}")
        return 0

    items = hist.get_last_turns(sid, limit_msgs=args.limit)
    if args.json:
        import json as _json
        print(_json.dumps(items, ensure_ascii=False, indent=2))
    else:
        if not items:
            print("Kayıt yok.")
            return 0
        for i, m in enumerate(items, 1):
            cit = " | ".join(m.get("citations") or [])
            print(f"[{i}] {m['role'].upper()} | intent={m.get('intent')} | sentiment={m.get('sentiment')} | tool={m.get('tool')}")
            print(m["content"])
            if cit:
                print("  citations:", cit)
            print("-" * 40)
    return 0

def _cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn  
    except Exception:
        print("Hata: 'uvicorn' yüklü değil. `pip install uvicorn` ile kurun.")
        return 2
    uvicorn.run(
        "src.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0

def main() -> int:
    p = argparse.ArgumentParser("Diyoloji - API & CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    # serve
    sp = sub.add_parser("serve", help="FastAPI sunucusunu başlat")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8000)
    sp.add_argument("--reload", action="store_true")
    sp.set_defaults(func=_cmd_serve)

    # ingest (JSON/JSONL)
    sp = sub.add_parser("ingest", help="JSON/JSONL → chunk/embed → Milvus'a yaz")
    sp.add_argument("--file", type=str, required=True, help="JSON/JSONL dosya veya klasör")
    sp.set_defaults(func=_cmd_ingest)

    # ask
    sp = sub.add_parser("ask", help="Soru sor ve RAG yanıtı al")
    sp.add_argument("query", type=str, help="Kullanıcı sorusu")
    sp.add_argument("--tool", type=str, default=None, choices=["billing", "roaming", "package", "coverage", "app"])
    sp.add_argument("--session", type=str, default=None, help="Session ID (opsiyonel). Boşsa yeni oluşturulur.")
    sp.add_argument("--json", action="store_true", help="JSON çıktı ver")
    sp.set_defaults(func=_cmd_ask)

    # history
    sp = sub.add_parser("history", help="Oturum geçmişini görüntüle/sil")
    sp.add_argument("--session", type=str, required=True, help="Session ID")
    sp.add_argument("--limit", type=int, default=50, help="Getirilecek maksimum mesaj sayısı")
    sp.add_argument("--clear", action="store_true", help="Geçmişi sil")
    sp.add_argument("--json", action="store_true", help="JSON çıktı ver")
    sp.set_defaults(func=_cmd_history)

    args = p.parse_args()
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
