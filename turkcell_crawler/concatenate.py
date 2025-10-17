#!/usr/bin/env python3
# Bir klasördeki .jsonl dosyalarını birleştirir.
# Varsayılan: sadece BUGÜN değişmiş .jsonl dosyalarını alıp db_turkcell.jsonl yazar.
# İsteğe bağlı:
#   --all    -> bugün filtresi olmadan tüm .jsonl dosyalarını ekle
#   --dedupe -> 'url' alanına göre tekilleştir

from pathlib import Path
from datetime import datetime
import argparse, json, re, sys

def is_today(path: Path) -> bool:
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return mtime.date() == datetime.now().date()

def numeric_prefix_key(path: Path):
    m = re.match(r"^(\d+)\.", path.name)
    return (int(m.group(1)) if m else 10**9, path.name)

def main():
    ap = argparse.ArgumentParser(description="Concatenate .jsonl files into db_turkcell.jsonl")
    ap.add_argument("--dir", default=".", help="Kaynak klasör (varsayılan: .)")
    ap.add_argument("--out", default="db_turkcell.jsonl", help="Çıktı dosyası adı")
    ap.add_argument("--all", action="store_true", help="Bugün filtresi olmadan tüm .jsonl dosyalarını dahil et")
    ap.add_argument("--dedupe", action="store_true", help="URL alanına göre tekilleştir")
    args = ap.parse_args()

    root = Path(args.dir)
    candidates = sorted(root.glob("*.jsonl"), key=numeric_prefix_key)

    if not args.all:
        candidates = [p for p in candidates if is_today(p)]

    if not candidates:
        print("Uyarı: Dahil edilecek .jsonl dosyası bulunamadı.", file=sys.stderr)
        return 0

    seen_urls = set()
    total_in = total_out = 0

    with open(args.out, "w", encoding="utf-8") as out:
        for p in candidates:
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s:
                        continue
                    total_in += 1
                    if args.dedupe:
                        try:
                            obj = json.loads(s)
                        except json.JSONDecodeError:
                            obj = None
                        if isinstance(obj, dict) and "url" in obj:
                            u = obj["url"]
                            if u in seen_urls:
                                continue
                            seen_urls.add(u)
                            out.write(json.dumps(obj, ensure_ascii=False) + "\n")
                            total_out += 1
                        else:
                            out.write(s + "\n")
                            total_out += 1
                    else:
                        out.write(s + "\n")
                        total_out += 1

    print(f"{len(candidates)} dosyadan {total_out}/{total_in} satır yazıldı → {args.out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
