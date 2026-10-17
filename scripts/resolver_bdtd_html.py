#!/usr/bin/env python3
"""
Resolve o ID do registro BDTD pela busca HTML do VuFind para itens que ainda
não têm `links.bdtd_registro`. Depois, `enriquecer_bdtd_registros.py` busca
resumo, palavras-chave e link de acesso na página do registro.

Uso:
    .venv/bin/python scripts/resolver_bdtd_html.py --limit 20
    .venv/bin/python scripts/resolver_bdtd_html.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "site/public/data/itens"
CACHE = ROOT / ".cache" / "bdtd-html-search"
REPORT = ROOT / "dados" / "bdtd_resolvidos.json"

BASE = "https://bdtd.ibict.br/vufind"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
session = requests.Session()
session.headers.update(HEADERS)

STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no", "na",
    "nos", "nas", "para", "por", "com", "um", "uma", "uns", "umas", "sobre",
    "como", "que", "se", "ao", "aos", "à", "às", "pelo", "pela",
}


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def surname(value: str) -> str:
    text = clean(value)
    if "," in text:
        return norm(text.split(",", 1)[0])
    parts = text.split()
    return norm(parts[-1]) if parts else ""


def queries(item: dict) -> list[str]:
    title = clean(item.get("titulo", ""))
    # Remove subtítulo muito longo, mas mantenha o título principal.
    main = clean(title.split(":", 1)[0])
    tokens = [re.sub(r"[^\wÀ-ÿ]", "", word) for word in title.split()]
    tokens = [word for word in tokens if word and word.lower() not in STOPWORDS]
    candidates = [
        title,
        main,
        " ".join(tokens),
        " ".join(tokens[:8]),
        " ".join(tokens[:6]),
        " ".join(sorted(tokens, key=len, reverse=True)[:5]),
        " ".join(sorted(tokens, key=len, reverse=True)[:4]),
    ]
    result = []
    for candidate in candidates:
        candidate = clean(candidate)
        if len(candidate) >= 12 and candidate not in result:
            result.append(candidate)
    return result[:6]


def cache_path(query: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(query.encode("utf-8")).hexdigest()
    return CACHE / f"{digest}.html"


def fetch_search(query: str) -> str:
    path = cache_path(query)
    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")
    url = f"{BASE}/Search/Results?lookfor={quote_plus(query)}&type=Title&limit=20"
    for attempt in range(3):
        try:
            response = session.get(url, timeout=30)
            if response.status_code == 200:
                path.write_text(response.text, encoding="utf-8")
                time.sleep(0.6)
                return response.text
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(3 * (attempt + 1))
                continue
            return ""
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return ""


def parse_results(html: str) -> list[dict]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for link in soup.select("a.title"):
        href = link.get("href") or ""
        match = re.search(r"/Record/([^/?#]+)", href)
        if not match:
            continue
        block = link.find_parent(class_="result-body") or link.parent
        text = clean(block.get_text(" | ", strip=True)) if block else ""
        author = ""
        author_match = re.search(r"\|\s*Por\s*\|\s*(.+?)\s*\|\s*Publicado", text)
        if author_match:
            author = clean(author_match.group(1))
        year_match = re.search(r"Publicado em\s*(\d{4})", text)
        results.append(
            {
                "id": match.group(1),
                "title": clean(link.get_text(" ")),
                "author": author,
                "year": year_match.group(1) if year_match else "",
                "url": f"{BASE}/Record/{match.group(1)}",
            }
        )
    return results


def score(item: dict, record: dict) -> tuple[float, float, bool]:
    title = similarity(item.get("titulo", ""), record.get("title", ""))
    author = False
    if item.get("autor") and record.get("author"):
        author = surname(item["autor"]) == surname(record["author"])
        if not author:
            author = similarity(surname(item["autor"]), surname(record["author"])) >= 0.88
    total = title + (0.08 if author else 0)
    if record.get("year") and str(item.get("ano", "")) == record["year"]:
        total += 0.04
    return total, title, author


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only", default="")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    files = sorted(ITEMS.glob("*.json"))
    if args.only:
        only = {value.strip() for value in args.only.split(",") if value.strip()}
        files = [path for path in files if path.stem in only]
    if not args.force:
        selected = []
        for path in files:
            item = json.loads(path.read_text(encoding="utf-8"))
            if not (item.get("links", {}).get("bdtd_registro")):
                selected.append(path)
        files = selected
    if args.limit:
        files = files[: args.limit]

    report = []
    for position, path in enumerate(files, start=1):
        item = json.loads(path.read_text(encoding="utf-8"))
        print(f"[{position}/{len(files)}] {item['id']} — {item.get('titulo', '')[:70]}", flush=True)

        found = {}
        for query in queries(item):
            html = fetch_search(query)
            for record in parse_results(html):
                found.setdefault(record["id"], record)
            if found:
                best_title = max(similarity(item.get("titulo", ""), record["title"]) for record in found.values())
                if best_title >= 0.94:
                    break

        ranked = sorted(((record, *score(item, record)) for record in found.values()), key=lambda entry: entry[1], reverse=True)
        if not ranked:
            print("  → nenhum resultado", flush=True)
            report.append({"id": item["id"], "status": "sem_resultado"})
            continue

        best, total, title_score, author_match = ranked[0]
        accepted = title_score >= 0.86 or (title_score >= 0.78 and author_match)
        if not accepted:
            print(f"  → descartado ({title_score:.2f}; autor={author_match}) {best['title'][:60]}", flush=True)
            report.append(
                {
                    "id": item["id"],
                    "status": "baixa_similaridade",
                    "score": round(title_score, 3),
                    "candidate": best["url"],
                }
            )
            continue

        item.setdefault("links", {})["bdtd_registro"] = best["url"]
        item["bdtd_api"] = {
            "status": "ok",
            "score": round(title_score, 3),
            "id": best["id"],
            "url": item["links"].get("registro_institucional") or item["links"].get("texto_completo") or "",
            "origem": "busca_html",
            "consultado_em": time.strftime("%Y-%m-%d"),
        }
        path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  → ok {title_score:.2f} | {best['id']} | {best['title'][:60]}", flush=True)
        report.append(
            {
                "id": item["id"],
                "status": "ok",
                "score": round(title_score, 3),
                "record": best["id"],
                "url": best["url"],
            }
        )

    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = sum(1 for entry in report if entry.get("status") == "ok")
    print(f"\n✓ {ok}/{len(report)} registros resolvidos pela busca HTML")


if __name__ == "__main__":
    main()
