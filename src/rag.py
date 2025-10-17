from __future__ import annotations

import json
import os
import time
from typing import List, Literal, Optional, Tuple, Dict

from openai import OpenAI
from pydantic import BaseModel

from .config import settings
from .project_pipeline import search, route_category_from_text
from . import history as hist
from .debug_logger import debug_log

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _norm_tool(t: Optional[str], chosen: Optional[str]) -> str:
    if t in VALID_TOOLS:
        return t
    if chosen in VALID_TOOLS:
        return chosen
    return "other"

def _norm_intent(i: Optional[str], tool_val: str) -> str:
    return i if i in VALID_TOOLS.union({"other"}) else tool_val

def _norm_sentiment(s: Optional[str], default_: str = "neutral") -> str:
    if not s:
        return default_
    s = s.strip().lower()
    mapping = {
        "negatif": "negative", "olumsuz": "negative",
        "pozitif": "positive", "olumlu": "positive",
        "nötr": "neutral", "notr": "neutral",
        "bilgilendirici": "neutral", "bilgi": "neutral", "info": "neutral",
    }
    if s in ("negative", "neutral", "positive"):
        return s
    return mapping.get(s, default_)

def _tr_lower(s: str) -> str:
    return (s or "").replace("İ", "i").replace("I", "ı").lower()

def _dedup(seq: List[str]) -> List[str]:
    seen, out = set(), []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out

def _truncate(s: str, max_chars: int) -> str:
    return s if len(s) <= max_chars else s[: max_chars - 3] + "..."

def _heuristic_boost(hits: List[Dict], query: str) -> List[Dict]:
    """Sorgu ile içerik/URL kelime eşleşmesi varsa ufak bonus ver (COSINE/IP için)."""
    q = _tr_lower(query)
    keysets = [
        ["devret", "devir", "sahip", "isim değiş"],
        ["fatura", "yüksek", "itiraz", "indirim", "ödeme", "odeme"],
        ["yurtdış", "roaming", "abroad", "uluslar"],
        ["kapsama", "çekim", "şebeke", "signal", "baz istasyonu"],
        ["dijital operatör", "uygulama", "giriş", "şifre", "login", "reset"],
    ]
    scored = []
    for h in hits:
        s = _tr_lower((h.get("text") or "") + " " + (h.get("url") or ""))
        bonus = 0.0
        for keys in keysets:
            if any(k in q and k in s for k in keys):
                bonus += 0.03
        hh = dict(h)
        # Not: Milvus IP/COSINE için 'score' zaten büyük-daha-iyi; buradaki bonus küçük tutuluyor.
        hh["score"] = float(h.get("score", 0.0)) + bonus
        scored.append(hh)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored

# --- Milvus skor normalizasyonu (metric'e göre) ---
def _normalize_and_filter_scores(
    hits: List[Dict],
    metric: str,
    keep_top: int,
    threshold: float = 0.0,
) -> List[Dict]:
    """
    Milvus distance/similarity davranışı:
    - COSINE/IP: büyük DAHA İYİ (Milvus 'distance' alanı pratikte similarity gibi davranır)
    - L2: küçük DAHA İYİ (distance) → sim = 1/(1+d)
    threshold: 0..1 arası sim eşiği (COSINE/IP için direkt; L2 için normalize sim)
    """
    if not hits:
        return []

    m = (metric or "").strip().upper()
    normed: List[Dict] = []

    if m in ("COSINE", "IP"):
        for h in hits:
            s = float(h.get("score", 0.0))
            hh = dict(h)
            hh["_norm"] = max(min(s, 1.0), -1.0)  # güvenli aralık
            normed.append(hh)
        normed.sort(key=lambda x: x["_norm"], reverse=True)
        if threshold and threshold > 0.0:
            normed = [h for h in normed if h["_norm"] >= threshold]
    else:
        # L2
        for h in hits:
            d = float(h.get("score", 0.0))
            sim = 1.0 / (1.0 + max(d, 0.0))
            hh = dict(h)
            hh["_norm"] = sim
            normed.append(hh)
        normed.sort(key=lambda x: x["_norm"], reverse=True)
        if threshold and threshold > 0.0:
            normed = [h for h in normed if h["_norm"] >= threshold]

    if not normed:
        normed = hits[:keep_top]
    return normed[:keep_top]

# ─────────────────────────────────────────────────────────────────────────────
# LangSmith tracing (opsiyonel)
try:
    from langsmith import traceable  # type: ignore
except Exception:
    def traceable(*args, **kwargs):  # no-op
        def _wrap(fn): return fn
        return _wrap

# ─────────────────────────────────────────────────────────────────────────────
# Guardrails adapter (src/guardrails.py)
_HAS_GUARDS = True
try:
    from .guardrails import INPUT_GUARD, STRUCT_GUARD, SafeGenOut  # type: ignore
except Exception:
    _HAS_GUARDS = False
    INPUT_GUARD = None
    STRUCT_GUARD = None
    SafeGenOut = None

# Soft-fail bayrağı (guard flag → reddetme, sadece logla ve devam et)
GUARD_SOFT_FAIL = os.getenv("GUARD_SOFT_FAIL", "true").lower() in ("1", "true", "yes", "on")

# Tek bir OpenAI client
_CLIENT = OpenAI(
    api_key=getattr(settings, "openai_api_key", ""),
    base_url=getattr(settings, "openai_base_url", None) or None,
)

# ─────────────────────────────────────────────────────────────────────────────
# Modeller
class ClsOut(BaseModel):
    intent: Literal["billing", "roaming", "package", "coverage", "app", "other"]
    sentiment: Literal["negative", "neutral", "positive"]

class GenOut(BaseModel):
    answer: str
    citations: List[str]
    tool: Literal["billing", "roaming", "package", "coverage", "app", "other"]
    intent: Literal["billing", "roaming", "package", "coverage", "app", "other"]
    sentiment: Literal["negative", "neutral", "positive"]

# ─────────────────────────────────────────────────────────────────────────────
# Router & yardımcılar
TOOL_KEYWORDS: Dict[str, List[str]] = {
    "billing":  ["fatura","ödeme","odeme","kesim","borç","borc","tahsilat","invoice","bill","faturam","ekstre"],
    "roaming":  [
        "yurtdışı","yurtdisi","roaming","uluslararası","uluslararasi","abroad","international","seyahat","dolaşım","dolasim",
        # ülke/bolge anahtarları
        "almanya","germany","avrupa","ab","fransa","italya","ingiltere","uk","ispanya","hollanda","austria","avusturya","isviçre","switzerland"
    ],
    "package": [
    "paket","tarife","dakika","internet","sms","ek paket","ekpaket","quota",
    "abonelik","devir","hat devri","hat taşıma","taşıma","iptal","iptali",
    "paket bitti","paketim bitti","paket satın al","paket al","paket yenile",
    "paket değiştir","paket degistir","paket yükselt","paket dusur","kampanya"],
    "coverage": ["kapsama","çekim","cekim","4.5g","5g","şebeke","sebeke","baz istasyonu","coverage","signal","çekmiyor","cek miyor","çekim gücü"],
    "app":      [
        "dijital operatör","dijital operator","uygulama","app","giriş","girış","giris","giremiyorum","şifre","sifre","login","reset",
        "başlatılamadı","crash","atıyor","atiyor","sürekli atıyor","donuyor","takılıyor","çöküyor","hata","açılmıyor","yavaş"
    ],
}
VALID_TOOLS = set(TOOL_KEYWORDS.keys())

# TR kaba filtre (guardrails yoksa)
HARASSMENT_TR: List[str] = [
    "salak","aptal","gerizekalı","gerizekali","eşek","mal","sığır","sigir","enayi","keriz",
    "ahmak","dangalak","şerefsiz","serefsiz","geri zekalı","geri zekali","rezil","aptalsınız","aptalsiniz",
]

def _keyword_route(q: str) -> Optional[str]:
    ql = _tr_lower(q)
    best, score = None, 0
    for tool, kws in TOOL_KEYWORDS.items():
        hits = sum(1 for k in kws if k in ql)
        if hits > score:
            best, score = tool, hits
    return best if score > 0 else None

# ─────────────────────────────────────────────────────────────────────────────
# Intent sınıflandırması
@debug_log(prefix="Classifier")
@traceable(name="classify")
def classify(query: str) -> Tuple[str, str]:
    # hızlı yol (ucuz) + basit sentiment kuralları
    neg_terms = ["şikayet","sikayet","yüksek geldi","yuksek geldi","haksız","sorun","çalışmıyor","calismiyor","iptal etmek istiyorum","memnun değilim"]
    pos_terms = ["teşekkür","tesekkur","harika","çalıştı","calisti","super","süper","super"]

    kw = _keyword_route(query)
    ql = _tr_lower(query)

    if any(t in ql for t in neg_terms):
        return (kw or "other"), "negative"
    if any(t in ql for t in pos_terms):
        return (kw or "other"), "positive"
    if kw:
        return kw, "neutral"

    # JSON-enforced LLM
    model = getattr(settings, "openai_chat_model", "gpt-4o-mini")
    sys = (
        "Yalnızca JSON döndür. Keys: intent, sentiment.\n"
        "intent ∈ [billing, roaming, package, coverage, app, other]\n"
        "sentiment ∈ [negative, neutral, positive]"
    )
    try:
        resp = _CLIENT.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": query},
            ],
        )
        obj = json.loads(resp.choices[0].message.content)
        out = ClsOut(**obj)
        return out.intent, out.sentiment
    except Exception:
        # son çare
        return _keyword_route(query) or "other", "neutral"

# ─────────────────────────────────────────────────────────────────────────────
# Ana RAG
@debug_log(prefix="RAG")
@traceable(name="ask")
def ask(query: str, force_tool: Optional[str] = None, session_id: Optional[str] = None) -> GenOut:
    print("\n=== RAG Pipeline Debug ===")
    print(f"Input query: {query}")
    print(f"Force tool: {force_tool}")
    print(f"Session ID: {session_id}")

    # 0) Eski oturumları temizle (best-effort)
    try:
        hist_ttl = int(getattr(settings, "session_ttl_days", 7))
        hist.purge_old(hist_ttl)
    except Exception as e:
        print(f"Warning - Could not purge old sessions: {str(e)}")

    # 1) Güvenlik kontrolü (Guardrails varsa önce o; yoksa TR kaba filtre) — SOFT-FAIL
    refused = False
    refusal_msg = "Üzgünüm, uygunsuz veya hakaret içeren taleplere yanıt veremem."
    guard_notes = ""

    if _HAS_GUARDS and INPUT_GUARD is not None:
        try:
            r = INPUT_GUARD.validate(query)
            if not r.validation_passed:
                guard_notes = str(getattr(r, "validated_output", "")) or "Input guard flagged."
                print(f"[GUARD][INPUT] flagged: {guard_notes}")
                if not GUARD_SOFT_FAIL:
                    refused = True
        except Exception as e:
            print(f"[GUARD][INPUT] error: {e}")
    else:
        ql = query.lower()
        if any(w in ql for w in HARASSMENT_TR):
            guard_notes = "Local harassment keyword match."
            print(f"[GUARD][INPUT] flagged: {guard_notes}")
            if not GUARD_SOFT_FAIL:
                refused = True

    if refused:
        if bool(getattr(settings, "history_enabled", True)) and session_id:
            try:
                hist.add_user_message(session_id, query, intent="other", sentiment="negative")
                hist.add_assistant_message(session_id, refusal_msg, tool="other", intent="other",
                                           sentiment="negative", citations=[])
            except Exception:
                pass
        return GenOut(answer=refusal_msg, citations=[], tool="other", intent="other", sentiment="negative")

    # 2) Classify & store
    print("\n=== Classification Step ===")
    try:
        intent, sentiment = classify(query)
        print(f"Classified intent: {intent}")
        print(f"Classified sentiment: {sentiment}")
        history_enabled = bool(getattr(settings, "history_enabled", True))
        if history_enabled and session_id:
            try:
                hist.add_user_message(session_id, query, intent=intent, sentiment=sentiment)
            except Exception as e:
                print(f"Warning - Could not add user message to history: {str(e)}")
    except Exception as e:
        print(f"Error in classification: {str(e)}")
        intent, sentiment = "other", "neutral"

    # 3) Tool seçimi (classifier → keyword → route fallback)
    print("\n=== Tool Selection & Search ===")
    kw_tool = _keyword_route(query)
    route_tool = route_category_from_text(query)
    print(f"Keyword-based tool: {kw_tool}")
    print(f"Route-based tool: {route_tool}")

    chosen: Optional[str] = (
    force_tool
    or kw_tool
    or route_tool
    or (intent if intent in VALID_TOOLS else None)
)
    print(f"Final chosen tool: {chosen}")

    max_docs = int(getattr(settings, "max_context_docs", 6) or 6)
    initial_k = max(2 * max_docs, 12)
    print(f"Searching with initial_k={initial_k}")

    # 4) Arama
    try:
        hits = search(query, category=chosen, top_k=initial_k)
        print(f"Found {len(hits)} initial hits")
    except Exception as e:
        print(f"Error in search: {str(e)}")
        raise

    # 5) Heuristik re-rank + normalize + threshold
    hits = _heuristic_boost(hits, query)
    score_thr = float(getattr(settings, "score_threshold", 0.20) or 0.0)
    use_hits = _normalize_and_filter_scores(
        hits=hits,
        metric=getattr(settings, "milvus_metric", "COSINE"),
        keep_top=max_docs,
        threshold=score_thr,
    )

    # 6) Geçmiş özeti
    history_msgs = []
    history_enabled = bool(getattr(settings, "history_enabled", True))
    history_max_turns = int(getattr(settings, "history_max_turns", 4))
    if history_enabled and session_id:
        try:
            history_msgs = hist.get_last_turns(session_id, limit_msgs=2 * history_max_turns)
        except Exception:
            history_msgs = []
    hist_str = "\n".join(f"{m['role'].upper()}: {_truncate(m['content'], 400)}" for m in history_msgs)
    hist_str = _truncate(hist_str, 1500) if hist_str else ""

    # 7) Context
    context_blocks, seen_urls = [], []
    for h in use_hits:
        url = (h.get("url") or "").strip()
        txt = (h.get("text") or "").strip()
        if url:
            seen_urls.append(url)
            context_blocks.append(
                f"[Kategori: {h.get('category', 'unknown')} | Benzerlik≈{h.get('_norm', 0.0):.2f}] URL: {url}\nTEXT: {_truncate(txt, 1400)}"
            )
    citations = _dedup(seen_urls)
    context_str = "\n\n---\n\n".join(context_blocks) if context_blocks else "(no context)"

    # 8) Üretim (Guardrails STRUCT_GUARD → yoksa JSON fallback + retry + rules)
    model = getattr(settings, "openai_chat_model", "gpt-4o-mini")
    outs: Optional[GenOut] = None

    # Context'i güvenli boyuta indir: ilk 4 blok
    MAX_BLOCKS = 4
    small_blocks = context_blocks[:MAX_BLOCKS]
    small_context_str = "\n\n---\n\n".join(small_blocks) if small_blocks else "(no context)"
    small_citations = _dedup(seen_urls[:MAX_BLOCKS])

    def _llm_json_call(sys_prompt: str, user_prompt: str) -> Dict:
        resp = _CLIENT.chat.completions.create(
            model=model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": sys_prompt},
                      {"role": "user", "content": user_prompt}],
        )
        return json.loads(resp.choices[0].message.content)

    def _rules_fallback_answer(
        q: str,
        hits_used: List[Dict],
        cits: List[str],
        chosen_tool: Optional[str],
    ) -> GenOut:
        """
        LLM üretimi başarısızsa kuralsal bir yanıt üret.
        İçerik ve adımlar 'chosen_tool' kategorisine göre gelir.
        """
        tool_val = chosen_tool if chosen_tool in VALID_TOOLS else "other"
        intent_val = tool_val
        out_cits = cits if (cits and isinstance(cits, list)) else []

        blob = " ".join([(h.get("text") or "") + " " + (h.get("url") or "") for h in hits_used]).lower()

        def std_answer(title: str, bullets: List[str], steps: List[str]) -> str:
            s = title + "\n" + "".join(f"- {b}\n" for b in bullets)
            s += "\nYapabileceklerin:\n" + "".join(f"{i+1}. {st}\n" for i, st in enumerate(steps))
            return s.strip()

        if tool_val == "app":
            # Uygulama / giriş problemleri fallback
            bullets = [
                "Sunucu yoğunluğu, ağ/geçici hata veya cihaz tarih/saat senkron sorunu olabilir.",
                "Hesap şifresi/OTP SMS engeli, çoklu cihaz oturumu veya eski sürüm kaynaklı olabilir.",
            ]
            steps = [
                "Uygulamayı güncelle, cihazı yeniden başlat.",
                "Wi-Fi/LTE değiştir, uçak modunu aç/kapat; mümkünse VPN kapalı dene.",
                "Ayarlar > Uygulamalar > Dijital Operatör > Önbelleği temizle / Zorla durdur.",
                "Şifreni sıfırla; OTP SMS’nin engellenmediğinden emin ol (mesaj filtreleri/operatör engelleri).",
                "Sorun sürerse hata ekranının saatiyle birlikte geri bildirim gönder.",
            ]
            ans = std_answer("Giriş yapamama sorunu için kontrol edilmesi gerekenler:", bullets, steps)

        elif tool_val == "roaming":
            bullets = [
                "Bulunduğun ülkede anlaşmalı operatör ve profil seçiminde sorun olabilir.",
                "Paketin bitmiş veya paket dışı ücretlendirme başlamış olabilir.",
            ]
            steps = [
                "Cihazda veri dolaşımı açık mı kontrol et.",
                "Operatör seçiminde 'Otomatik'i kapatıp önerilen partneri elle seç.",
                "Dijital Operatör’den ülke/paket durumunu ve kullanımını kontrol et.",
                "Gerekirse yurt dışı ek paket satın al.",
            ]
            ans = std_answer("Yurt dışı kullanımıyla ilgili kontrol listesi:", bullets, steps)

        elif tool_val == "package":
            bullets = [
                "Paketin bitişi sonrası paket dışı ücretlendirme başlamış olabilir.",
                "Kampanya/paket değişimi kısmi dönem ücretini tetiklemiş olabilir.",
            ]
            steps = [
                "Dijital Operatör’den kalanları ve paket bitiş tarihini kontrol et.",
                "Gerekiyorsa ek paket satın al veya tarifeni yükselt.",
                "Paket dışı kullanım uyarılarını aç (SMS/bildirim).",
                "Detay kullanım dökümünde beklenmeyen bir kalem varsa destekle iletişime geç.",
            ]
            ans = std_answer("Paket bitimi/ekstra ücretlendirme için öneriler:", bullets, steps)

        elif tool_val == "billing":
            bullets = [
                "Paket aşımı, roaming, abonelikli servisler, Paycell işlemleri, cihaz taksidi veya vergi farkı kaynaklı olabilir.",
            ]
            steps = [
                "Dijital Operatör > Faturalarım’da kalem dökümünü incele.",
                "Paket Dışı/Abonelik/Paycell/Önceki dönem kalemi var mı bak.",
                "Şüpheli kalem için Faturaya İtiraz adımlarını uygula.",
            ]
            ans = std_answer("Faturan yüksek görünmüş olabilir. Yaygın nedenler:", bullets, steps)

        else:
            bullets = ["Sorunu anlamak için daha fazla bağlama ihtiyaç var."]
            steps = [
                "Kullandığın hizmet/paket ve gördüğün hata mesajını paylaş.",
                "Öncesinde yaptığın adımları kısaca yaz.",
            ]
            ans = std_answer("Netleştirmek için:", bullets, steps)

        return GenOut(
            answer=ans,
            citations=out_cits,
            tool=tool_val,
            intent=intent_val,
            sentiment="negative",  # fallback'te varsayılan
        )

    # Guardrails yolu (varsa)
    if _HAS_GUARDS and STRUCT_GUARD is not None and SafeGenOut is not None:
        try:
            sys = (
                "You are Diyoloji. Yanıtını **yalnızca Türkçe** ver.\n"
                "Sadece CONTEXT'i kullan; uydurma bilgi verme. Yetersizse net söyle ve sonraki adımı öner.\n"
                "Kısa, maddeli ve eyleme dönük yaz. Çıktıyı JSON üret (answer, citations, tool, intent, sentiment)."
            )
            user = (
                (f"KISA GEÇMİŞ:\n{hist_str}\n\n" if hist_str else "")
                + f"KULLANICI SORUSU:\n{query}\n\nCONTEXT:\n{small_context_str}"
            )
            resp = STRUCT_GUARD(
                llm_api=_CLIENT.chat.completions.create,
                model=model,
                temperature=0.0,
                messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
            )
            if resp.validation_passed and resp.validated_output:
                data = resp.validated_output  # SafeGenOut
                answer = getattr(data, "answer", "") or "Bağlam sınırlı; aşağıdaki adımları deneyebilirsin."
                cits = (getattr(data, "citations", None) or small_citations) or []
                tool_val = getattr(data, "tool", None)
                final_tool = tool_val if tool_val in VALID_TOOLS else (chosen if (chosen in VALID_TOOLS) else "other")
                outs = GenOut(
                    answer=answer.strip(),
                    citations=_dedup(list(cits)),
                    tool=final_tool,
                    intent=intent if intent in VALID_TOOLS.union({"other"}) else "other",
                    sentiment=sentiment,
                )
            else:
                print("[GUARD][OUTPUT] struct guard failed; falling back to plain JSON generation.")
                outs = None
        except Exception as e:
            print(f"[GEN][guardrails] error: {e}")
            outs = None

    # JSON-only çağrı + retry
    if outs is None:
        sys = (
            "You are Diyoloji. Answer ONLY in Turkish. Use ONLY the given CONTEXT; "
            "if insufficient, say so and propose the closest next step. "
            "Return JSON only: {answer:str, citations:list[str], tool:str, intent:str, sentiment:str}. "
            "STYLE: bullets for steps; short, actionable."
        )
        user = (
            (f"ÖNCEKİ KONUŞMA (kısa):\n{hist_str}\n\n" if hist_str else "")
            + f"KULLANICI SORUSU:\n{query}\n\nCONTEXT:\n{small_context_str}"
        )

        obj: Optional[Dict] = None
        try:
            obj = _llm_json_call(sys, user)
        except Exception as e:
            print(f"[GEN][json_v1] error: {e}")
            # Retry: daha da küçültülmüş context ve basit prompt
            try:
                tiny_blocks = small_blocks[:2]
                tiny_context = "\n\n---\n\n".join(tiny_blocks) if tiny_blocks else "(no context)"
                obj = _llm_json_call(sys, (f"KULLANICI SORUSU:\n{query}\n\nCONTEXT:\n{tiny_context}"))
            except Exception as e2:
                print(f"[GEN][json_retry] error: {e2}")
                outs = _rules_fallback_answer(query, use_hits, small_citations,chosen)

        if outs is None and isinstance(obj, dict):
            # defaults
            obj.setdefault("citations", small_citations)
            obj_tool = obj.get("tool", None)
            if obj_tool not in VALID_TOOLS:
                obj["tool"] = (chosen if chosen in VALID_TOOLS else "other")
            obj_intent = obj.get("intent", intent)
            if obj_intent not in VALID_TOOLS.union({"other"}):
                obj["intent"] = "other"
            obj.setdefault("sentiment", sentiment)
            if not (obj.get("answer") or "").strip():
                obj["answer"] = "Bağlam sınırlı; aşağıdaki adımları deneyebilirsin."
            try:
                outs = GenOut(**obj)
            except Exception as e3:
                print(f"[GEN][construct] error: {e3}")
                outs = _rules_fallback_answer(query, use_hits, small_citations, chosen)

    # 9) Geçmişe yaz (sadece SQLite history; indekse upsert KALDIRILDI)
    history_enabled = bool(getattr(settings, "history_enabled", True))
    if history_enabled and session_id:
        try:
            hist.add_assistant_message(
                session_id,
                outs.answer,
                tool=outs.tool,
                intent=outs.intent,
                sentiment=outs.sentiment,
                citations=outs.citations,
            )
        except Exception:
            pass

    return outs
