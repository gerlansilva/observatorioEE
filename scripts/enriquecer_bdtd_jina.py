#!/usr/bin/env python3
"""
Lê os registros da BDTD via Jina Reader quando o host bdtd.ibict.br está
indisponível na rede local. O conteúdo continua sendo o HTML oficial do
VuFind; o Jina apenas faz a intermediação da requisição.

Uso:
    .venv/bin/python scripts/enriquecer_bdtd_jina.py --limit 10
    .venv/bin/python scripts/enriquecer_bdtd_jina.py
    .venv/bin/python scripts/enriquecer_bdtd_jina.py --resolve-missing
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from enriquecer_bdtd_registros import (
    BASE,
    clean,
    is_full_name,
    is_url,
    make_tags,
    natural_name,
    parse_record,
    valid_abstract,
)

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "site/public/data/itens"
CACHE = ROOT / ".cache" / "bdtd-jina"
REPORT = ROOT / "dados" / "bdtd_jina.json"

JINA = "https://r.jina.ai/http://bdtd.ibict.br/vufind"
HEADERS = {
    "X-Return-Format": "html",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}
session = requests.Session()
session.headers.update(HEADERS)

STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no", "na",
    "nos", "nas", "para", "por", "com", "um", "uma", "uns", "umas", "sobre",
    "como", "que", "se", "ao", "aos", "à", "às", "pelo", "pela",
}


def cache_path(kind: str, key: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return CACHE / f"{kind}-{digest}.html"


def fetch(url: str, cache_key: str, force: bool = False) -> str:
    path = cache_path("record" if "/Record/" in url else "search", cache_key)
    if path.exists() and not force:
        return path.read_text(encoding="utf-8", errors="ignore")
    for attempt in range(4):
        try:
            response = session.get(url, timeout=70)
            if response.status_code == 200 and len(response.text) > 1000:
                path.write_text(response.text, encoding="utf-8")
                time.sleep(1.6)
                return response.text
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(4 * (attempt + 1))
                continue
            return ""
        except requests.RequestException:
            time.sleep(3 * (attempt + 1))
    return ""


def record_url(record_id: str) -> str:
    return f"{JINA}/Record/{record_id}"


def record_id(item: dict) -> str:
    url = item.get("links", {}).get("bdtd_registro") or ""
    if url:
        return url.rstrip("/").rsplit("/", 1)[-1]
    return str(item.get("bdtd_api", {}).get("id") or "")


def apply_record(item: dict, record: dict, rid: str) -> dict:
    item.setdefault("links", {})["bdtd_registro"] = f"{BASE}/{rid}"

    abstract = clean(record.get("abstract", ""))
    if abstract and not valid_abstract(abstract):
        abstract = ""
    if abstract:
        language = detect_language(abstract)
        if not (language == "eng" and item.get("resumo_idioma") == "por" and item.get("resumo")):
            item["resumo"] = abstract
            item["resumo_idioma"] = language
            item["resumo_fonte"] = f"{BASE}/{rid}"

    tags = make_tags(record)
    existing_tags = item.get("tags", [])
    use_bdtd_tags = bool(tags) and (
        not existing_tags
        or len(tags) >= 3
        or (len(tags) >= 2 and not all(tag.isupper() for tag in tags))
    )
    if use_bdtd_tags:
        item["tags"] = tags
        item["palavras_chave_bdtd"] = "; ".join(tags)

    access = record.get("access_link", "")
    if is_url(access):
        if access.lower().endswith(".pdf"):
            item["links"]["texto_completo"] = access
        else:
            item["links"]["registro_institucional"] = access

    if record.get("author") and is_full_name(record["author"]):
        if "," in item.get("autor", "") or not is_full_name(item.get("autor", "")):
            item["autor_planilha"] = item.get("autor_planilha") or item.get("autor", "")
            item["autor"] = record["author"]
    if record.get("advisor") and is_full_name(record["advisor"]):
        if not item.get("orientador") or "," in item.get("orientador", ""):
            item["orientador"] = record["advisor"]

    if record.get("year") and len(record["year"]) == 4:
        item["ano_bdtd"] = int(record["year"])
    if record.get("type"):
        item["tipo_bdtd"] = record["type"]
    if record.get("institution"):
        item["instituicao_bdtd"] = record["institution"]
    if record.get("program"):
        item["programa_bdtd"] = record["program"]

    item["bdtd_registro"] = {
        "status": "ok",
        "id": rid,
        "url": f"{BASE}/{rid}",
        "fonte": "jina-reader",
        "consultado_em": time.strftime("%Y-%m-%d"),
    }
    return {
        "id": item["id"],
        "status": "ok",
        "record": rid,
        "abstract_chars": len(abstract),
        "tags": len(tags),
        "access": access,
    }


def detect_language(text: str) -> str:
    if not text:
        return ""
    portuguese = len(
        re.findall(r"\b(este|esta|esse|essa|trabalho|pesquisa|objetivo|investiga|análise|resultados|ensino)\b", text.lower())
    )
    english = len(
        re.findall(r"\b(this|study|research|aim|objective|results|teaching|learning|work)\b", text.lower())
    )
    if portuguese >= english and portuguese > 0:
        return "por"
    if english > 0:
        return "eng"
    return ""


def search_queries(item: dict) -> list[str]:
    title = clean(item.get("titulo", ""))
    main = clean(title.split(":", 1)[0])
    tokens = [re.sub(r"[^\wÀ-ÿ]", "", word) for word in title.split()]
    tokens = [word for word in tokens if word and word.lower() not in STOPWORDS]
    candidates = [
        title,
        main,
        " ".join(tokens),
        " ".join(tokens[:8]),
        " ".join(sorted(tokens, key=len, reverse=True)[:5]),
    ]
    return list(dict.fromkeys(candidate for candidate in candidates if len(candidate) >= 12))[:5]


def parse_search(html: str) -> list[dict]:
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
            }
        )
    return results


def title_similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher

    def norm(value: str) -> str:
        import unicodedata

        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
        return re.sub(r"\s+", " ", text).strip()

    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def resolve_missing(item: dict, max_queries: int = 5) -> str:
    found = {}
    for query in search_queries(item)[:max_queries]:
        url = f"{JINA}/Search/Results?lookfor={quote_plus(query)}&type=Title&limit=20"
        html = fetch(url, f"search:{query}")
        for record in parse_search(html):
            found.setdefault(record["id"], record)
    if not found:
        return ""
    ranked = sorted(
        ((record, title_similarity(item.get("titulo", ""), record["title"])) for record in found.values()),
        key=lambda pair: pair[1],
        reverse=True,
    )
    best, score = ranked[0]
    author_match = False
    if item.get("autor") and best.get("author"):
        def surname(value: str) -> str:
            text = clean(value)
            if "," in text:
                return text.split(",", 1)[0].lower()
            return text.split()[-1].lower() if text.split() else ""

        author_match = surname(item["autor"]) == surname(best["author"])
    if score >= 0.86 or (score >= 0.80 and author_match):
        return best["id"]
    return ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--resolve-missing", action="store_true")
    parser.add_argument("--missing-only", action="store_true", help="só itens ainda sem ID BDTD")
    parser.add_argument("--max-queries", type=int, default=5)
    args = parser.parse_args()

    files = sorted(ITEMS.glob("*.json"))
    if args.missing_only:
        selected = []
        for path in files:
            item = json.loads(path.read_text(encoding="utf-8"))
            if not item.get("links", {}).get("bdtd_registro"):
                selected.append(path)
        files = selected
    if args.only:
        only = {value.strip() for value in args.only.split(",") if value.strip()}
        files = [path for path in files if path.stem in only]
    if args.limit:
        files = files[: args.limit]

    report = []
    for position, path in enumerate(files, start=1):
        item = json.loads(path.read_text(encoding="utf-8"))
        rid = record_id(item)
        if not rid and args.resolve_missing:
            print(f"[{position}/{len(files)}] {item['id']} — buscando ID…", flush=True)
            rid = resolve_missing(item, max_queries=args.max_queries)
            if not rid:
                report.append({"id": item["id"], "status": "nao_encontrado"})
                continue
            print(f"  → BDTD {rid}", flush=True)
        if not rid:
            report.append({"id": item["id"], "status": "sem_registro_bdtd"})
            continue

        print(f"[{position}/{len(files)}] {item['id']} — BDTD {rid}", flush=True)
        html = fetch(record_url(rid), f"record:{rid}", force=args.force)
        record = parse_record(html)
        if not record or not (record.get("abstract") or record.get("keywords_pt") or record.get("access_link")):
            print("  → sem dados extraíveis", flush=True)
            report.append({"id": item["id"], "status": "sem_dados", "record": rid})
            continue

        result = apply_record(item, record, rid)
        path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            f"  → resumo {result['abstract_chars']} | tags {result['tags']} | acesso {result['access'] or '—'}",
            flush=True,
        )
        report.append(result)

    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = sum(1 for entry in report if entry.get("status") == "ok")
    print(f"\n✓ {ok}/{len(report)} registros com dados do BDTD (via Jina Reader)")


if __name__ == "__main__":
    main()
