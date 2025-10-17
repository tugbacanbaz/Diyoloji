import os, csv, json
from typing import List, Dict
from statistics import mean
from src.project_pipeline import search, route_category_from_text
from src.config import settings

def norm(s: str) -> str:
    return " ".join((s or "").lower().split())

def em(pred: str, gold: str) -> float:
    return 1.0 if norm(pred) == norm(gold) else 0.0

def substr(pred: str, gold: str) -> float:
    g = norm(gold); p = norm(pred)
    return 1.0 if g and g in p else 0.0

def load_eval(path: str) -> List[Dict]:
    items = []
    if path.endswith(".jsonl"):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
    else:
        with open(path, "r", encoding="utf-8") as f:
            r = csv.DictReader(f)
            items = list(r)
    return items

def pick_answer(hits: List[Dict]) -> str:
    if not hits:
        return ""
    return (hits[0].get("text") or "")[:600]

def run_eval(path: str, k: int, save_errors: str = None):
    data = load_eval(path)
    ems, subs, rec, route_acc = [], [], [], []
    errors = []

    for i, ex in enumerate(data, 1):
        q = ex.get("question") or ex.get("query") or ""
        gold = ex.get("expected") or ex.get("answer") or ""
        gold_cat = ex.get("category") or None

        # router (fallback)
        routed = gold_cat or route_category_from_text(q)
        hits = search(q, category=routed, top_k=k)

        pred = pick_answer(hits)
        ems.append(em(pred, gold))
        subs.append(substr(pred, gold))
        rec.append(1.0 if hits else 0.0)

        # category doğruluğu (varsa)
        if gold_cat:
            route_acc.append(1.0 if (routed == gold_cat) else 0.0)

        # hata örneklerini topla
        if not hits or substr(pred, gold) < 1.0:
            errors.append({
                "question": q,
                "gold": gold,
                "gold_category": gold_cat or "",
                "routed_category": routed or "",
                "top_hit_url": hits[0]["url"] if hits else "",
                "top_hit_snippet": (hits[0]["text"][:200] if hits and hits[0].get("text") else ""),
            })

        if i % 20 == 0:
            print(f"[{i}/{len(data)}] EM:{mean(ems):.3f} Sub:{mean(subs):.3f} R@{k}:{mean(rec):.3f}"
                  + (f" RouteAcc:{mean(route_acc):.3f}" if route_acc else ""))

    print("\n==== Final ====")
    print(f"EM: {mean(ems):.3f}")
    print(f"Substring: {mean(subs):.3f}")
    print(f"Recall@{k}: {mean(rec):.3f}")
    if route_acc:
        print(f"RouteAcc: {mean(route_acc):.3f}")

    if save_errors:
        with open(save_errors, "w", encoding="utf-8") as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)
        print(f"Saved errors → {save_errors}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--k", type=int, default=int(getattr(settings, "max_context_docs", 6) or 6))
    ap.add_argument("--save-errors", type=str, default="eval_errors.json")
    args = ap.parse_args()
    run_eval(args.file, k=args.k, save_errors=args.save_errors)
