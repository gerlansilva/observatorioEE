#!/usr/bin/env python3
"""
Resolve registros BDTD pela API JSON via Jina Reader e já busca a página do
registro para extrair resumo, palavras-chave e link de acesso.

Uso:
    .venv/bin/python scripts/resolver_bdtd_jina_api.py --limit 10
    .venv/bin/python scripts/resolver_bdtd_jina_api.py
"""

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote_plus

import requests

from enriquecer_bdtd_jina import apply_record, fetch, record_url
from enriquecer_bdtd_registros import clean, parse_record

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "site/public/data/itens"
REPORT = ROOT / "dados" / "bdtd_jina_api.json"

JINA = "https://r.jina.ai/http://bdtd.ibict.br/vufind"
session = requests.Session()
session.headers.update({"X-Return-Format": "text", "User-Agent": "Mozilla/5.0"})

STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no", "na",
    "nos", "nas", "para", "por", "com", "um", "uma", "uns", "umas", "sobre",
    "como", "que", "se", "ao", "aos", "à", "às", "pelo", "pela",
}


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
    main = clean(title.split(":", 1)[0])
    tokens = [re.sub(r"[^\wÀ-ÿ]", "", word) for word in title.split()]
    tokens = [word for word in tokens if word and word.lower() not in STOPWORDS]
    candidates = [
        title,
        main,
        " ".join(sorted(tokens, key=len, reverse=True)[:5]),
        " ".join(tokens[:7]),
    ]
    return list(dict.fromkeys(candidate for candidate in candidates if len(candidate) >= 12))[:3]


def search_api(query: str) -> dict:
    url = (
        f"{JINA}/api/v1/search?lookfor={quote_plus(query)}"
        "&type=AllFields&limit=20"
    )
    for attempt in range(3):
        try:
            response = session.get(url, timeout=70)
            if response.status_code == 200:
                text = response.text.strip()
                start, end = text.find("{"), text.rfind("}")
                if start >= 0 and end > start:
                    return json.loads(text[start : end + 1])
                return {}
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(4 * (attempt + 1))
                continue
            return {}
        except (requests.RequestException, json.JSONDecodeError):
            time.sleep(3 * (attempt + 1))
    return {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only", default="")
    args = parser.parse_args()

    files = sorted(ITEMS.glob("*.json"))
    if args.only:
        only = {value.strip() for value in args.only.split(",") if value.strip()}
        files = [path for path in files if path.stem in only]
    else:
        files = [
            path
            for path in files
            if not json.loads(path.read_text(encoding="utf-8")).get("links", {}).get("bdtd_registro")
        ]
    if args.limit:
        files = files[: args.limit]

    report = []
    for position, path in enumerate(files, start=1):
        item = json.loads(path.read_text(encoding="utf-8"))
        print(f"[{position}/{len(files)}] {item['id']} — {item.get('titulo', '')[:70]}", flush=True)

        found = {}
        for query in queries(item):
            data = search_api(query)
            for record in data.get("records", []):
                found.setdefault(record.get("id"), record)
            if found:
                best_title = max(similarity(item.get("titulo", ""), record.get("title", "")) for record in found.values())
                if best_title >= 0.95:
                    break

        ranked = []
        for record in found.values():
            title_score = similarity(item.get("titulo", ""), record.get("title", ""))
            authors = record.get("authors", {}).get("primary", {})
            record_author = next(iter(authors), "")
            author_match = bool(record_author) and surname(item.get("autor", "")) == surname(record_author)
            ranked.append((record, title_score + (0.06 if author_match else 0), title_score, author_match))
        ranked.sort(key=lambda entry: entry[1], reverse=True)

        if not ranked:
            print("  → nenhum resultado", flush=True)
            report.append({"id": item["id"], "status": "sem_resultado"})
            continue

        best, total, title_score, author_match = ranked[0]
        if not (title_score >= 0.86 or (title_score >= 0.80 and author_match)):
            print(f"  → descartado ({title_score:.2f}) {best.get('title', '')[:60]}", flush=True)
            report.append({"id": item["id"], "status": "baixa_similaridade", "score": round(title_score, 3)})
            continue

        rid = best["id"]
        item.setdefault("links", {})["bdtd_registro"] = f"https://bdtd.ibict.br/vufind/Record/{rid}"
        html = fetch(record_url(rid), f"record:{rid}")
        record = parse_record(html)
        if record and (record.get("abstract") or record.get("keywords_pt") or record.get("access_link")):
            result = apply_record(item, record, rid)
            print(
                f"  → ok {title_score:.2f} | resumo {result['abstract_chars']} | tags {result['tags']} | {result['access'] or '—'}",
                flush=True,
            )
        else:
            print(f"  → link ok {title_score:.2f}, página sem dados extraíveis", flush=True)
        path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report.append(
            {
                "id": item["id"],
                "status": "ok",
                "score": round(title_score, 3),
                "record": rid,
                "author_match": author_match,
            }
        )

    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = sum(1 for entry in report if entry.get("status") == "ok")
    print(f"\n✓ {ok}/{len(report)} registros resolvidos pela API BDTD via Jina")


if __name__ == "__main__":
    main()
