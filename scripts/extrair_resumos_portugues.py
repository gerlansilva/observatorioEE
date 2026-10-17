#!/usr/bin/env python3
"""
Busca o resumo em português na página do repositório institucional quando a
BDTD só oferece o abstract em inglês. Não traduz nem inventa texto: apenas
substitui quando encontra um resumo português na fonte original.
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
CACHE = ROOT / ".cache" / "resumos-pt"
REPORT = ROOT / "dados" / "resumos_portugues.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
session = requests.Session()
session.headers.update(HEADERS)

BLOCKED = ("tede2.pucsp.br",)


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def cache_path(url: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / f"{hashlib.sha1(url.encode()).hexdigest()}.html"


def fetch(url: str) -> str:
    if any(domain in url for domain in BLOCKED):
        return ""
    path = cache_path(url)
    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")
    for attempt in range(2):
        try:
            response = session.get(url, timeout=20, allow_redirects=True)
            if response.status_code == 200 and "text/html" in response.headers.get("content-type", ""):
                path.write_text(response.text, encoding="utf-8")
                time.sleep(0.55)
                return response.text
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 * (attempt + 1))
                continue
            return ""
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return ""


def language(text: str) -> str:
    text = text.lower()
    pt = len(
        re.findall(
            r"\b(este|esta|esse|essa|trabalho|pesquisa|objetivo|investiga|análise|resultados|ensino|aprendizagem|alunos|professores|dados)\b",
            text,
        )
    )
    en = len(
        re.findall(
            r"\b(this|study|research|aim|objective|results|teaching|learning|students|teachers|data|work)\b",
            text,
        )
    )
    if pt >= en and pt >= 2:
        return "por"
    if en > pt:
        return "eng"
    return ""


def extract(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []

    for meta in soup.find_all("meta"):
        name = (meta.get("name") or meta.get("property") or "").lower()
        if not any(key in name for key in ("abstract", "description", "resumo")):
            continue
        content = clean(meta.get("content"))
        if len(content) >= 200 and not content.lower().startswith(("http://", "https://")):
            candidates.append(content)

    for selector in (
        "#resumo",
        ".resumo",
        ".item-abstract",
        ".abstract",
        "div[class*='resumo']",
        "div[class*='abstract']",
        "blockquote.abstract",
    ):
        for element in soup.select(selector):
            content = clean(element.get_text(" "))
            if len(content) >= 200:
                candidates.append(content)

    for content in candidates:
        if language(content) == "por":
            # Evita capturar o abstract em inglês repetido em metadados.
            return content[:6000]
    return ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only", default="")
    args = parser.parse_args()

    files = sorted(ITEMS.glob("*.json"))
    if args.only:
        only = {value.strip() for value in args.only.split(",") if value.strip()}
        files = [path for path in files if path.stem in only]
    files = [
        path
        for path in files
        if json.loads(path.read_text(encoding="utf-8")).get("resumo_idioma") != "por"
    ]
    if args.limit:
        files = files[: args.limit]

    report = []
    found = 0
    for position, path in enumerate(files, start=1):
        item = json.loads(path.read_text(encoding="utf-8"))
        links = item.get("links", {})
        urls = [links.get("registro_institucional"), links.get("texto_completo")]
        urls = [url for url in urls if isinstance(url, str) and url.startswith(("http://", "https://"))]
        urls = [url for url in dict.fromkeys(urls) if not re.search(r"\.pdf(?:$|\?)", url, re.I)]
        if not urls:
            report.append({"id": item["id"], "status": "sem_url"})
            continue

        print(f"[{position}/{len(files)}] {item['id']} — {urls[0]}", flush=True)
        abstract = ""
        used = ""
        for url in urls[:2]:
            abstract = extract(fetch(url))
            if abstract:
                used = url
                break
        if not abstract:
            print("  → sem resumo em português", flush=True)
            report.append({"id": item["id"], "status": "nao_encontrado"})
            continue

        if item.get("resumo") and item.get("resumo_idioma") == "eng":
            item["resumo_eng"] = item["resumo"]
        item["resumo"] = abstract
        item["resumo_idioma"] = "por"
        item["resumo_fonte"] = used
        path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        found += 1
        print(f"  → resumo em português ({len(abstract)} caracteres)", flush=True)
        report.append({"id": item["id"], "status": "ok", "url": used, "chars": len(abstract)})

    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n✓ {found}/{len(files)} resumos em português localizados no repositório")


if __name__ == "__main__":
    main()
