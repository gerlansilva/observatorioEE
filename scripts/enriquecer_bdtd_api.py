#!/usr/bin/env python3
"""
Enriquece os registros com a API JSON da BDTD: link do repositório institucional,
link do registro na BDTD, nome completo do autor, tipo e palavras-chave.

Uso:
    .venv/bin/python scripts/enriquecer_bdtd_api.py --limit 10
    .venv/bin/python scripts/enriquecer_bdtd_api.py

A API fica em https://bdtd.ibict.br/vufind/api/v1/search.
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

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "site/public/data/itens"
CACHE = ROOT / ".cache" / "bdtd-api"
REPORT = ROOT / "dados" / "enriquecimento_bdtd.json"

BASE = "https://bdtd.ibict.br/vufind"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; repositorio-educacao-estatistica/1.0)"}
session = requests.Session()
session.headers.update(HEADERS)

STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas",
    "para", "por", "com", "um", "uma", "uns", "umas", "sobre", "como", "que", "se", "ao", "aos",
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


def natural_name(value: str) -> str:
    text = clean(value)
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if len(parts) >= 2:
        return " ".join([parts[1], parts[0], *parts[2:]])
    return text


def is_full_name(value: str) -> bool:
    words = clean(value).split()
    return len(words) >= 2 and sum(1 for word in words if len(word) > 2) >= 2


def cache_path(term: str) -> Path:
    digest = hashlib.sha1(term.encode("utf-8")).hexdigest()
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / f"{digest}.json"


def search(term: str, force: bool = False) -> dict:
    path = cache_path(term)
    if path.exists() and not force:
        return json.loads(path.read_text(encoding="utf-8"))

    url = (
        f"{BASE}/api/v1/search?lookfor={quote_plus(term)}&type=AllFields&limit=20"
    )
    for attempt in range(4):
        try:
            response = session.get(url, timeout=40)
            if response.status_code == 200:
                data = response.json()
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                time.sleep(0.35)
                return data
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(3 * (attempt + 1))
                continue
            return {}
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return {}


def queries(item: dict) -> list[str]:
    title = item["titulo"]
    tokens = [re.sub(r"[^\wÀ-ÿ]", "", word) for word in clean(title).split()]
    tokens = [word for word in tokens if word and word.lower() not in STOPWORDS]
    result = [title]
    if tokens:
        result.append(" ".join(sorted(tokens, key=len, reverse=True)[:4]))
        result.append(" ".join(sorted(tokens, key=len, reverse=True)[:3]))
        result.append(" ".join(tokens[1:6]))
        result.append(" ".join(tokens[2:7]))
    return list(dict.fromkeys(query for query in result if query.strip()))


def score(item: dict, record: dict) -> float:
    title_score = similarity(item["titulo"], record.get("title", ""))
    authors = record.get("authors", {}).get("primary", {})
    record_author = next(iter(authors), "")
    author_score = 0.0
    if record_author:
        if surname(item.get("autor", "")) == surname(record_author):
            author_score = 1.0
        elif SequenceMatcher(None, surname(item.get("autor", "")), surname(record_author)).ratio() >= 0.85:
            author_score = 1.0
    return 0.8 * title_score + 0.2 * author_score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--missing-only", action="store_true", help="só registros sem link de repositório")
    parser.add_argument("--no-bdtd-only", action="store_true", help="só registros ainda sem link BDTD")
    args = parser.parse_args()

    files = sorted(ITEMS.glob("*.json"))
    if args.only:
        only = {value.strip() for value in args.only.split(",") if value.strip()}
        files = [path for path in files if path.stem in only]
    if args.no_bdtd_only:
        files = [
            path for path in files
            if not json.loads(path.read_text(encoding="utf-8")).get("links", {}).get("bdtd_registro")
        ]
    if args.missing_only:
        filtered = []
        for path in files:
            item = json.loads(path.read_text(encoding="utf-8"))
            links = item.get("links", {})
            if not (links.get("registro_institucional") or links.get("texto_completo")):
                filtered.append(path)
        files = filtered
    if args.limit:
        files = files[: args.limit]

    report = []
    for position, path in enumerate(files, start=1):
        item = json.loads(path.read_text(encoding="utf-8"))
        if item.get("bdtd_api", {}).get("status") == "ok" and not args.force:
            continue
        print(f"[{position}/{len(files)}] {item['id']} — {item['titulo'][:65]}…", flush=True)

        found = {}
        for query in queries(item):
            data = search(query, force=args.force)
            for record in data.get("records", []):
                found.setdefault(record.get("id"), record)
            if found:
                best_title = max(similarity(item["titulo"], record.get("title", "")) for record in found.values())
                if best_title >= 0.93:
                    break

        ranked = sorted(((record, score(item, record)) for record in found.values()), key=lambda pair: pair[1], reverse=True)
        best, best_score = ranked[0] if ranked else (None, 0.0)
        title_score = similarity(item["titulo"], best.get("title", "")) if best else 0

        if not best or (best_score < 0.75 and title_score < 0.85):
            item["bdtd_api"] = {"status": "nao_encontrado", "score": round(best_score, 3)}
            path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"  → não encontrado ({best_score:.2f})", flush=True)
            report.append({"id": item["id"], "status": "nao_encontrado", "score": round(best_score, 3)})
            continue

        links = item.setdefault("links", {})
        urls = [entry.get("url") for entry in best.get("urls", []) if entry.get("url")]
        repository = next((url for url in urls if url.startswith(("http://", "https://"))), "")
        if repository:
            if repository.lower().endswith((".pdf", ".pdf?download=1")):
                links["texto_completo"] = repository
            else:
                links["registro_institucional"] = repository
        links["bdtd_registro"] = f"{BASE}/Record/{best['id']}"

        authors = best.get("authors", {}).get("primary", {})
        author_citation = next(iter(authors), "")
        author = natural_name(author_citation)
        if is_full_name(author) and ("," in item.get("autor", "") or not is_full_name(item.get("autor", ""))):
            item["autor_planilha"] = item.get("autor_planilha") or item.get("autor", "")
            item["autor"] = author

        formats = best.get("formats", [])
        if "doctoralThesis" in formats:
            item["tipo"] = "Tese"
            item["grau"] = "Doutorado"
        elif "masterThesis" in formats:
            item["tipo"] = "Dissertação"
            if item.get("grau") == "Doutorado":
                item["grau"] = "Mestrado Acadêmico"

        subjects = []
        for group in best.get("subjects", []):
            for subject in group:
                subject = clean(subject)
                if subject and not subject.startswith("CNPQ::") and subject not in subjects:
                    subjects.append(subject)
        if subjects and not clean(item.get("palavras_chave")):
            item["palavras_chave_bdtd"] = "; ".join(subjects[:20])

        item["bdtd_api"] = {
            "status": "ok",
            "score": round(best_score, 3),
            "id": best.get("id"),
            "url": repository,
            "consultado_em": time.strftime("%Y-%m-%d"),
        }
        path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  → ok {best_score:.2f} | {repository or 'sem URL de repositório'}", flush=True)
        report.append(
            {
                "id": item["id"],
                "status": "ok",
                "score": round(best_score, 3),
                "repository": repository,
                "bdtd": item["bdtd_api"]["url"],
            }
        )

    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = sum(1 for entry in report if entry.get("status") == "ok")
    print(f"\n✓ {ok}/{len(report)} registros com dados da BDTD")


if __name__ == "__main__":
    main()
