#!/usr/bin/env python3
"""
Enriquece cada registro com a página do BDTD (VuFind):
- resumo/abstract;
- palavras-chave em português;
- link de acesso do repositório institucional;
- autor, orientador, ano, tipo, instituição e programa (quando disponíveis).

Uso:
    .venv/bin/python scripts/enriquecer_bdtd_registros.py --limit 10
    .venv/bin/python scripts/enriquecer_bdtd_registros.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "site/public/data/itens"
CACHE = ROOT / ".cache" / "bdtd-records"
REPORT = ROOT / "dados" / "bdtd_registros.json"

BASE = "https://bdtd.ibict.br/vufind/Record"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
session = requests.Session()
session.headers.update(HEADERS)
LOWER_WORDS = {"de", "da", "do", "das", "dos", "e"}


def clean(value) -> str:
    text = str(value or "").replace("\xa0", " ")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def norm(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").lower()).strip()
    return text


def natural_name(value: str) -> str:
    text = clean(value)
    if not text or "não informado" in text.lower():
        return ""
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if len(parts) >= 2:
        result = " ".join([parts[1], parts[0], *parts[2:]])
        if text.isupper():
            return smart_case(result)
        return result
    return smart_case(text) if text.isupper() else text


def smart_case(value: str) -> str:
    text = clean(value).lower()
    if not text:
        return ""
    words = []
    for index, word in enumerate(text.split()):
        if index > 0 and word in LOWER_WORDS:
            words.append(word)
        else:
            words.append(word[:1].upper() + word[1:])
    return " ".join(words)


def is_full_name(value: str) -> bool:
    words = clean(value).split()
    return len(words) >= 2 and sum(1 for word in words if len(word) > 2) >= 2


def is_url(value) -> bool:
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def cache_path(record_id: str) -> Path:
    digest = hashlib.sha1(record_id.encode("utf-8")).hexdigest()
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / f"{digest}.html"


def fetch(record_id: str, force: bool = False, cached_only: bool = False) -> str:
    path = cache_path(record_id)
    if path.exists() and not force:
        return path.read_text(encoding="utf-8", errors="ignore")
    if cached_only:
        return ""
    url = f"{BASE}/{record_id}"
    for attempt in range(3):
        try:
            response = session.get(url, timeout=25)
            if response.status_code == 200:
                path.write_text(response.text, encoding="utf-8")
                time.sleep(0.8)
                return response.text
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(3 * (attempt + 1))
                continue
            return ""
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return ""


def parse_record(html: str) -> dict:
    if not html:
        return {}
    soup = BeautifulSoup(html, "html.parser")
    data = {}
    for table in soup.find_all("table"):
        if "Detalhes bibliográficos" not in table.get_text(" ", strip=True):
            continue
        for row in table.find_all("tr"):
            header = row.find("th")
            cell = row.find("td")
            if not header or not cell:
                continue
            key = clean(header.get_text(" ")).rstrip(":")
            if "Palavras-chave" in key:
                values = [clean(a.get_text(" ")) for a in cell.find_all("a")]
                if not values:
                    values = [clean(line) for line in cell.get_text("\n").splitlines() if clean(line)]
                data[key] = values
            else:
                data[key] = clean(cell.get_text(" "))
        break

    # O "Resumo" fica fora das <tr> em algumas páginas do VuFind; usa regex.
    match = re.search(r"<th>\s*Resumo:\s*</th>\s*<td[^>]*>(.*?)</td>", html, re.S | re.I)
    if match:
        data["Resumo"] = clean(match.group(1))

    return {
        "title": data.get("Título", ""),
        "author": natural_name(data.get("Autor(a) principal", "")),
        "author_citation": clean(data.get("Autor(a) principal", "")),
        "advisor": natural_name(data.get("Orientador(a)", "")),
        "advisor_citation": clean(data.get("Orientador(a)", "")),
        "year": clean(data.get("Ano de defesa", ""))[:4],
        "type": clean(data.get("Tipo de documento", "")),
        "institution": clean(data.get("Instituição de defesa", "")),
        "program": clean(data.get("Programa de Pós-Graduação", "")),
        "access_link": clean(data.get("Link de acesso", "")),
        "abstract": clean(data.get("Resumo", "")),
        "keywords_pt": [clean(value) for value in data.get("Palavras-chave em Português", []) if clean(value)],
        "keywords_en": [clean(value) for value in data.get("Palavras-chave em Inglês", []) if clean(value)],
    }


def valid_abstract(text: str) -> bool:
    text = clean(text)
    if len(text) < 150:
        return False
    lowered = text.lower()
    if lowered.startswith(
        (
            "orientador",
            "dissertação",
            "tese",
            "não informado",
            "resumo não",
            "resumo:",
        )
    ):
        return False
    return True


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


def make_tags(record: dict) -> list[str]:
    source = record.get("keywords_pt") or []
    tags = []
    seen = set()
    for value in source:
        value = clean(value).strip(" .;,")
        if not value or value.lower().startswith("cnpq::"):
            continue
        if value.isupper() and len(value.split()) >= 3:
            continue
        key = norm(value)
        if key in seen:
            continue
        seen.add(key)
        tags.append(value)
    return tags[:24]


def record_id(item: dict) -> str:
    url = item.get("links", {}).get("bdtd_registro") or ""
    if url:
        return url.rstrip("/").rsplit("/", 1)[-1]
    return str(item.get("bdtd_api", {}).get("id") or "")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--cached-only", action="store_true", help="não faz novas requisições; usa apenas o cache")
    args = parser.parse_args()

    files = sorted(ITEMS.glob("*.json"))
    if args.only:
        only = {value.strip() for value in args.only.split(",") if value.strip()}
        files = [path for path in files if path.stem in only]
    if args.limit:
        files = files[: args.limit]

    report = []
    processed = 0
    for position, path in enumerate(files, start=1):
        item = json.loads(path.read_text(encoding="utf-8"))
        rid = record_id(item)
        if not rid:
            report.append({"id": item["id"], "status": "sem_registro_bdtd"})
            continue

        print(f"[{position}/{len(files)}] {item['id']} — BDTD {rid}", flush=True)
        html = fetch(rid, force=args.force, cached_only=args.cached_only)
        record = parse_record(html)
        if not record or not record.get("abstract") and not record.get("keywords_pt") and not record.get("access_link"):
            print("  → sem dados extraíveis", flush=True)
            report.append({"id": item["id"], "status": "sem_dados", "record": rid})
            continue
        processed += 1

        item["links"] = item.get("links", {})
        item["links"]["bdtd_registro"] = f"{BASE}/{rid}"

        abstract = record.get("abstract", "")
        abstract_language = detect_language(abstract)
        if abstract and not valid_abstract(abstract):
            print(f"  → resumo inválido ignorado ({len(abstract)} caracteres)", flush=True)
            abstract = ""
        if abstract:
            existing_language = item.get("resumo_idioma", "")
            if not (abstract_language == "eng" and existing_language == "por" and item.get("resumo")):
                item["resumo"] = abstract
                item["resumo_idioma"] = abstract_language
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
            "consultado_em": time.strftime("%Y-%m-%d"),
        }
        path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            f"  → resumo {len(abstract)} | tags {len(tags)} | acesso {access or '—'}",
            flush=True,
        )
        report.append(
            {
                "id": item["id"],
                "status": "ok",
                "record": rid,
                "abstract_chars": len(abstract),
                "tags": len(tags),
                "access": access,
            }
        )

    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n✓ {processed} registros processados com dados do BDTD")


if __name__ == "__main__":
    main()
