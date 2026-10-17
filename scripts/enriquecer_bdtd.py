#!/usr/bin/env python3
"""
Enriquece os registros com dados da BDTD (Biblioteca Digital Brasileira de Teses e
Dissertações): nome completo do autor, orientação, resumo, palavras-chave e links.

Uso:
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/python scripts/enriquecer_bdtd.py --limit 5
    .venv/bin/python scripts/enriquecer_bdtd.py

O script é retomável: usa cache em .cache/bdtd e ignora registros já enriquecidos
(use --force para refazer).
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
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "site/public/data"
ITEMS = DATA / "itens"
INDEX = DATA / "indice.json"
REPORT = ROOT / "dados" / "enriquecimento.json"
CACHE = ROOT / ".cache" / "bdtd"

BASE = "https://bdtd.ibict.br"
SEARCH = BASE + "/vufind/Search/Results"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

session = requests.Session()
session.headers.update(HEADERS)


def clean(value) -> str:
    text = str(value or "").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def surname(author: str) -> str:
    text = clean(author)
    if "," in text:
        return norm(text.split(",", 1)[0])
    parts = text.split()
    return norm(parts[-1]) if parts else ""


def natural_name(value: str) -> str:
    text = clean(value)
    if not text or "não informado" in text.lower():
        return ""
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if len(parts) >= 2:
        # "Lima, Felipe Mascagna Bittencourt" -> "Felipe Mascagna Bittencourt Lima"
        return " ".join([parts[1], parts[0], *parts[2:]])
    return text


def is_informed(value: str) -> bool:
    text = clean(value).lower()
    return bool(text) and "não informado" not in text and "nao informado" not in text


def cache_path(kind: str, key: str) -> Path:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    directory = CACHE / kind
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{digest}.html"


def fetch(url: str, kind: str, key: str, force: bool = False) -> str:
    path = cache_path(kind, key)
    if path.exists() and not force:
        return path.read_text(encoding="utf-8", errors="ignore")

    for attempt in range(4):
        try:
            response = session.get(url, timeout=40)
            if response.status_code == 200:
                path.write_text(response.text, encoding="utf-8")
                time.sleep(1.1)
                return response.text
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(4 * (attempt + 1))
                continue
            return ""
        except requests.RequestException:
            time.sleep(3 * (attempt + 1))
    return ""


def parse_results(html: str) -> list[dict]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()
    for link in soup.select('a[href^="/vufind/Record/"]'):
        href = link.get("href") or ""
        record_id = href.rsplit("/", 1)[-1]
        if not record_id or record_id in seen:
            continue
        title = clean(link.get_text(" "))
        if len(title) < 8:
            continue
        seen.add(record_id)
        results.append(
            {
                "record_id": record_id,
                "url": urljoin(BASE, href),
                "title": title,
            }
        )
    return results


def search_records(title: str, author: str) -> list[dict]:
    queries = [f'"{title}"', title, f'{title} {surname(author)}']
    collected = {}
    for query in queries:
        url = f"{SEARCH}?lookfor={quote_plus(query)}&type=AllFields"
        html = fetch(url, "search", query)
        results = parse_results(html)
        for result in results:
            collected.setdefault(result["record_id"], result)
        if results:
            best = max(similarity(title, result["title"]) for result in results)
            if best >= 0.78:
                break
    return list(collected.values())


def parse_record(html: str) -> dict:
    if not html:
        return {}
    soup = BeautifulSoup(html, "html.parser")
    table = None
    for candidate in soup.find_all("table"):
        if "Detalhes bibliográficos" in candidate.get_text(" ", strip=True):
            table = candidate
            break
    if not table:
        return {}

    data = {}
    for row in table.find_all("tr"):
        header = row.find("th")
        cell = row.find("td")
        if not header or not cell:
            continue
        key = clean(header.get_text(" "))
        key = key.rstrip(":")
        if "Palavras-chave" in key:
            values = [clean(a.get_text(" ")) for a in cell.find_all("a")]
            if not values:
                values = [clean(line) for line in cell.get_text("\n").splitlines() if clean(line)]
            data[key] = values
        else:
            data[key] = clean(cell.get_text(" "))

    meta = {}
    for tag in soup.find_all("meta"):
        name = tag.get("name") or ""
        content = tag.get("content") or ""
        if name.lower().startswith(("dc.", "citation_")) and content:
            meta[name] = clean(content)

    creator = data.get("Autor(a) principal") or meta.get("DC.creator") or meta.get("citation_author")
    advisor = data.get("Orientador(a)") or ""
    year = data.get("Ano de defesa") or meta.get("DC.issued") or meta.get("citation_date")
    doc_type = data.get("Tipo de documento") or meta.get("DC.type")
    institution = data.get("Instituição de defesa") or ""
    program = data.get("Programa de Pós-Graduação") or ""
    access_link = data.get("Link de acesso") or ""
    abstract = data.get("Resumo") or meta.get("DC.description") or ""
    keywords_pt = data.get("Palavras-chave em Português") or []
    keywords_en = data.get("Palavras-chave em Inglês") or []

    return {
        "title": data.get("Título") or meta.get("DC.title") or meta.get("citation_title") or "",
        "author_citation": clean(creator),
        "author": natural_name(creator),
        "advisor_citation": clean(advisor),
        "advisor": natural_name(advisor),
        "year": clean(year)[:4],
        "type": clean(doc_type),
        "institution": clean(institution),
        "program": clean(program),
        "access_link": clean(access_link),
        "abstract": clean(abstract),
        "keywords_pt": [clean(value) for value in keywords_pt if clean(value)],
        "keywords_en": [clean(value) for value in keywords_en if clean(value)],
    }


def score_candidate(item: dict, result: dict, record: dict | None = None) -> float:
    title_score = similarity(item["titulo"], result["title"])
    if record and record.get("title"):
        title_score = max(title_score, similarity(item["titulo"], record["title"]))

    author_score = 0.0
    if record and record.get("author"):
        item_surname = surname(item.get("autor", ""))
        record_surname = surname(record.get("author_citation", ""))
        if item_surname and record_surname:
            author_score = 1.0 if item_surname == record_surname else 0.0

    year_score = 0.0
    if record and record.get("year") and item.get("ano"):
        year_score = 1.0 if str(item["ano"]) == str(record["year"]) else 0.0

    return 0.7 * title_score + 0.2 * author_score + 0.1 * year_score


def enrich_item(item: dict, force: bool = False) -> dict:
    if item.get("bdtd", {}).get("status") == "ok" and not force:
        return item

    results = search_records(item["titulo"], item.get("autor", ""))
    if not results:
        item["bdtd"] = {"status": "nao_encontrado", "consultado_em": time.strftime("%Y-%m-%d")}
        return item

    ranked = sorted(
        ((result, similarity(item["titulo"], result["title"])) for result in results),
        key=lambda pair: pair[1],
        reverse=True,
    )[:4]

    best = None
    best_score = 0.0
    for result, title_score in ranked:
        if title_score < 0.62:
            continue
        html = fetch(result["url"], "record", result["record_id"], force=force)
        record = parse_record(html)
        if not record:
            continue
        score = score_candidate(item, result, record)
        if score > best_score:
            best = (result, record)
            best_score = score

    if not best or best_score < 0.78:
        item["bdtd"] = {
            "status": "baixa_confianca",
            "score": round(best_score, 3),
            "candidato": best[0]["url"] if best else None,
            "consultado_em": time.strftime("%Y-%m-%d"),
        }
        return item

    result, record = best
    item["autor_planilha"] = item.get("autor", "")
    item["orientador_planilha"] = item.get("orientador", "")

    capes_ok = item.get("capes", {}).get("status") == "ok"
    if record.get("author") and (not capes_ok or "," in item.get("autor", "")):
        item["autor"] = record["author"]
        item["autor_citacao"] = record["author_citation"]
    if record.get("advisor") and (not capes_ok or not item.get("orientador")):
        item["orientador"] = record["advisor"]
        item["orientador_citacao"] = record["advisor_citation"]
    if record.get("year") and len(record["year"]) == 4:
        item["ano"] = int(record["year"])
    if record.get("type") and record["type"].lower() in ("tese", "dissertação", "dissertacao"):
        item["tipo"] = "Tese" if record["type"].lower() == "tese" else "Dissertação"
    if record.get("abstract"):
        item["resumo_bdtd"] = record["abstract"]
    if record.get("keywords_pt"):
        item["palavras_chave_bdtd"] = "; ".join(record["keywords_pt"])
        if not clean(item.get("palavras_chave")):
            item["palavras_chave"] = item["palavras_chave_bdtd"]
    if record.get("institution"):
        item["instituicao_bdtd"] = record["institution"]
    if record.get("program"):
        item["programa_bdtd"] = record["program"]

    links = item.setdefault("links", {})
    links["bdtd_registro"] = result["url"]
    if str(record.get("access_link", "")).startswith(("http://", "https://")):
        links["texto_completo"] = record["access_link"]
    links.setdefault("google_scholar", links.get("google_scholar", ""))

    item["bdtd"] = {
        "status": "ok",
        "score": round(best_score, 3),
        "record_id": result["record_id"],
        "url": result["url"],
        "consultado_em": time.strftime("%Y-%m-%d"),
    }
    return item


def rebuild_index_entry(index_entry: dict, item: dict) -> dict:
    entry = dict(index_entry)
    entry["autor"] = item.get("autor", entry.get("autor", ""))
    entry["autor_planilha"] = item.get("autor_planilha", entry.get("autor_planilha", ""))
    entry["orientador"] = item.get("orientador", entry.get("orientador", ""))
    entry["ano"] = item.get("ano", entry.get("ano"))
    entry["tipo"] = item.get("tipo", entry.get("tipo"))
    if item.get("palavras_chave_bdtd") and not clean(entry.get("palavras_chave")):
        entry["palavras_chave"] = item["palavras_chave_bdtd"]
    if item.get("resumo_bdtd") and not clean(entry.get("resumo")):
        entry["resumo"] = item["resumo_bdtd"][:360]

    link = item.get("links", {}).get("texto_completo") or item.get("links", {}).get("bdtd_registro")
    entry["link"] = link or ""
    entry["bdtd_url"] = item.get("links", {}).get("bdtd_registro", "")

    search_parts = [
        entry.get("titulo", ""),
        entry.get("autor", ""),
        entry.get("autor_planilha", ""),
        entry.get("instituicao", ""),
        entry.get("orientador", ""),
        entry.get("programa", ""),
        entry.get("area", ""),
        entry.get("nivel", ""),
        entry.get("foco", ""),
        entry.get("conteudo", ""),
        entry.get("palavras_chave", ""),
        entry.get("resumo", ""),
        item.get("resumo_bdtd", ""),
        item.get("palavras_chave_bdtd", ""),
    ]
    entry["busca"] = clean(" ".join(str(part) for part in search_parts if part)).lower()
    entry["busca_norm"] = norm(entry["busca"])
    return entry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="limita a quantidade de registros")
    parser.add_argument("--force", action="store_true", help="ignora cache e refaz registros já enriquecidos")
    parser.add_argument("--only", default="", help="lista de IDs separada por vírgula")
    args = parser.parse_args()

    index = json.loads(INDEX.read_text(encoding="utf-8"))
    by_id = {entry["id"]: entry for entry in index}
    only = {value.strip() for value in args.only.split(",") if value.strip()}

    item_files = sorted(ITEMS.glob("*.json"))
    if only:
        item_files = [path for path in item_files if path.stem in only]
    if args.limit:
        item_files = item_files[: args.limit]

    report = []
    total = len(item_files)
    for position, path in enumerate(item_files, start=1):
        item = json.loads(path.read_text(encoding="utf-8"))
        print(f"[{position}/{total}] {item['id']} — {item['titulo'][:70]}…", flush=True)
        try:
            enriched = enrich_item(item, force=args.force)
        except Exception as error:  # noqa: BLE001 - relatório de falhas individuais
            print(f"  ! erro: {error}", flush=True)
            report.append({"id": item["id"], "status": "erro", "erro": str(error)})
            continue

        path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if item["id"] in by_id:
            by_id[item["id"]] = rebuild_index_entry(by_id[item["id"]], enriched)

        status = enriched.get("bdtd", {}).get("status", "?")
        score = enriched.get("bdtd", {}).get("score")
        print(f"  → {status} {score if score is not None else ''}", flush=True)
        report.append(
            {
                "id": item["id"],
                "status": status,
                "score": score,
                "autor": enriched.get("autor"),
                "orientador": enriched.get("orientador"),
                "url": enriched.get("bdtd", {}).get("url"),
                "link": enriched.get("links", {}).get("texto_completo"),
            }
        )

        INDEX.write_text(
            json.dumps(list(by_id.values()), ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = sum(1 for entry in report if entry.get("status") == "ok")
    print(f"\n✓ {ok}/{len(report)} registros enriquecidos com a BDTD")
    print(f"  relatório: {REPORT}")


if __name__ == "__main__":
    main()
