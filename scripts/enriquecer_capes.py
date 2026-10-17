#!/usr/bin/env python3
"""
Completa os registros com dados do Catálogo de Teses e Dissertações da CAPES:
nome completo do autor, orientação, ano, grau, instituição, programa e link.

Uso:
    .venv/bin/python scripts/enriquecer_capes.py --limit 5
    .venv/bin/python scripts/enriquecer_capes.py

O script é retomável e usa cache em .cache/capes.
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
DATA = ROOT / "site/public/data"
ITEMS = DATA / "itens"
INDEX = DATA / "indice.json"
REPORT = ROOT / "dados" / "enriquecimento_capes.json"
CACHE = ROOT / ".cache" / "capes"

BASE = "https://catalogodeteses.capes.gov.br/catalogo-teses"
SEARCH = BASE + "/rest/busca"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Origin": BASE,
    "Referer": BASE + "/",
}

session = requests.Session()
session.headers.update(HEADERS)

LOWER_WORDS = {"de", "da", "do", "das", "dos", "e"}


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


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


def smart_name(value: str) -> str:
    text = clean(value).lower()
    if not text:
        return ""
    parts = []
    for index, word in enumerate(text.split()):
        if index > 0 and word in LOWER_WORDS:
            parts.append(word)
        else:
            parts.append(word[:1].upper() + word[1:])
    return " ".join(parts)


def is_url(value: str) -> bool:
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def normalize_degree(value: str) -> str:
    text = clean(value).lower()
    if "doutor" in text:
        return "Doutorado"
    if "profissional" in text:
        return "Mestrado Profissional"
    if "mestrado" in text:
        return "Mestrado Acadêmico"
    return clean(value)


def cache_path(term: str) -> Path:
    digest = hashlib.sha1(term.encode("utf-8")).hexdigest()
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / f"{digest}.json"


def search(term: str, force: bool = False) -> dict:
    path = cache_path(term)
    if path.exists() and not force:
        return json.loads(path.read_text(encoding="utf-8"))

    payload = {
        "termo": term,
        "filtros": [],
        "pagina": 1,
        "registrosPorPagina": 20,
    }
    for attempt in range(4):
        try:
            response = session.post(SEARCH, json=payload, timeout=45)
            if response.status_code == 200:
                data = response.json()
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                time.sleep(0.45)
                return data
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(4 * (attempt + 1))
                continue
            return {}
        except requests.RequestException:
            time.sleep(3 * (attempt + 1))
    return {}


STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas",
    "para", "por", "com", "um", "uma", "uns", "umas", "sobre", "como", "que", "se", "ao", "aos",
}


def query_list(item: dict) -> list[str]:
    title = item["titulo"]
    author = item.get("autor", "")
    tokens = [re.sub(r"[^\wÀ-ÿ]", "", word) for word in clean(title).split()]
    tokens = [word for word in tokens if word and word.lower() not in STOPWORDS]
    queries = [title]
    if tokens:
        queries.append(" ".join(tokens[:8]))
        queries.append(" ".join(sorted(tokens, key=len, reverse=True)[:4]))
        queries.append(" ".join(sorted(tokens, key=len, reverse=True)[:3]))
    if author:
        author_surname = surname(author)
        if len(author_surname) >= 4:
            queries.append(author_surname)
        queries.append(f"{author_surname} {item.get('ano', '')}".strip())
    return list(dict.fromkeys(query for query in queries if query.strip()))


def candidates(item: dict) -> list[dict]:
    title = item["titulo"]
    found = {}
    for query in query_list(item):
        data = search(query)
        for record in data.get("tesesDissertacoes", []):
            found.setdefault(str(record.get("id")), record)
        if found:
            best = max(similarity(title, record.get("titulo", "")) for record in found.values())
            if best >= 0.93:
                break
    return list(found.values())


def advisor_from(data: dict) -> str:
    for aggregation in data.get("agregacoes", []):
        if aggregation.get("campo") == "Orientador":
            values = aggregation.get("agregados", [])
            if len(values) == 1:
                return smart_name(values[0].get("valor", ""))
    return ""


def author_match(value: str, candidate: str) -> float:
    a = surname(value)
    b_name = norm(candidate)
    if not a or not b_name:
        return 0.0
    a_tokens = [token for token in a.split() if len(token) > 1]
    b_tokens = set(b_name.split())
    if a_tokens and all(token in b_tokens for token in a_tokens):
        return 1.0
    # A planilha tem erros de grafia (ex.: BARRIZON / BARIZON).
    if any(SequenceMatcher(None, a, token).ratio() >= 0.85 for token in b_tokens):
        return 1.0
    return 0.0


def score(item: dict, record: dict) -> float:
    title_score = similarity(item["titulo"], record.get("titulo", ""))
    author_score = author_match(item.get("autor", ""), record.get("autor", ""))
    year_score = 0.0
    record_year = str(record.get("dataDefesa", ""))[:4]
    if record_year and item.get("ano"):
        year_score = 1.0 if str(item["ano"]) == record_year else 0.0
    return 0.7 * title_score + 0.2 * author_score + 0.1 * year_score


def enrich(item: dict, force: bool = False) -> dict:
    if item.get("capes", {}).get("status") == "ok" and not force:
        return item

    records = candidates(item)
    if not records:
        item["capes"] = {"status": "nao_encontrado", "consultado_em": time.strftime("%Y-%m-%d")}
        return item

    ranked = sorted(((record, score(item, record)) for record in records), key=lambda pair: pair[1], reverse=True)
    best, best_score = ranked[0]
    title_similarity = similarity(item["titulo"], best.get("titulo", ""))
    if best_score < 0.78 and title_similarity < 0.92:
        item["capes"] = {
            "status": "baixa_confianca",
            "score": round(best_score, 3),
            "candidato": best.get("link"),
            "consultado_em": time.strftime("%Y-%m-%d"),
        }
        return item

    item["autor_planilha"] = item.get("autor_planilha") or item.get("autor", "")
    item["orientador_planilha"] = item.get("orientador_planilha") or item.get("orientador", "")

    author = smart_name(best.get("autor", ""))
    if author:
        item["autor"] = author
        item["autor_capes"] = clean(best.get("autor", ""))
    if best.get("nomePrograma"):
        item["programa_capes"] = smart_name(best["nomePrograma"])
    if best.get("instituicao"):
        item["instituicao_capes"] = smart_name(best["instituicao"])
    if best.get("municipioPrograma"):
        item["cidade_capes"] = smart_name(best["municipioPrograma"])
    if best.get("dataDefesa"):
        item["ano"] = int(str(best["dataDefesa"])[:4])
    degree = normalize_degree(best.get("grauAcademico", ""))
    if degree:
        item["grau"] = degree
        item["tipo"] = "Tese" if degree == "Doutorado" else "Dissertação"
    # A API não devolve o orientador no objeto principal; ele aparece nas agregações.
    # Consulta o termo do título novamente para obter a agregação correspondente.
    advisor = ""
    for query in query_list(item):
        data = search(query)
        if any(str(record.get("id")) == str(best.get("id")) for record in data.get("tesesDissertacoes", [])):
            advisor = advisor_from(data)
            break
    if advisor:
        item["orientador"] = advisor
        item["orientador_capes"] = advisor

    item["capes"] = {
        "status": "ok",
        "score": round(best_score, 3),
        "id": str(best.get("id")),
        "consultado_em": time.strftime("%Y-%m-%d"),
    }
    return item


def rebuild_index_entry(entry: dict, item: dict) -> dict:
    entry = dict(entry)
    entry["autor"] = item.get("autor", entry.get("autor", ""))
    entry["autor_planilha"] = item.get("autor_planilha", entry.get("autor_planilha", ""))
    entry["orientador"] = item.get("orientador", entry.get("orientador", ""))
    entry["ano"] = item.get("ano", entry.get("ano"))
    entry["tipo"] = item.get("tipo", entry.get("tipo"))
    entry["grau"] = item.get("grau", entry.get("grau"))

    links = item.get("links", {})
    entry["link"] = (
        links.get("texto_completo")
        or links.get("bdtd_registro")
        or entry.get("link", "")
    )

    search_parts = [
        entry.get("titulo", ""),
        entry.get("autor", ""),
        entry.get("autor_planilha", ""),
        entry.get("instituicao", ""),
        item.get("instituicao_capes", ""),
        entry.get("orientador", ""),
        entry.get("programa", ""),
        item.get("programa_capes", ""),
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
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--only", default="")
    args = parser.parse_args()

    index = json.loads(INDEX.read_text(encoding="utf-8"))
    by_id = {entry["id"]: entry for entry in index}
    only = {value.strip() for value in args.only.split(",") if value.strip()}

    files = sorted(ITEMS.glob("*.json"))
    if only:
        files = [path for path in files if path.stem in only]
    if args.limit:
        files = files[: args.limit]

    report = []
    for position, path in enumerate(files, start=1):
        item = json.loads(path.read_text(encoding="utf-8"))
        print(f"[{position}/{len(files)}] {item['id']} — {item['titulo'][:65]}…", flush=True)
        try:
            enriched = enrich(item, force=args.force)
        except Exception as error:  # noqa: BLE001
            print(f"  ! erro: {error}", flush=True)
            report.append({"id": item["id"], "status": "erro", "erro": str(error)})
            continue

        path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if item["id"] in by_id:
            by_id[item["id"]] = rebuild_index_entry(by_id[item["id"]], enriched)

        status = enriched.get("capes", {}).get("status")
        print(
            f"  → {status} {enriched.get('capes', {}).get('score', '')} | {enriched.get('autor', '')}",
            flush=True,
        )
        report.append(
            {
                "id": item["id"],
                "status": status,
                "score": enriched.get("capes", {}).get("score"),
                "autor": enriched.get("autor"),
                "orientador": enriched.get("orientador"),
                "url": enriched.get("capes", {}).get("url"),
            }
        )
        INDEX.write_text(
            json.dumps(list(by_id.values()), ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = sum(1 for entry in report if entry.get("status") == "ok")
    print(f"\n✓ {ok}/{len(report)} registros enriquecidos com a CAPES")
    print(f"  relatório: {REPORT}")


if __name__ == "__main__":
    main()
