#!/usr/bin/env python3
"""
Extrai o resumo/abstract das páginas dos repositórios institucionais e grava em `resumo`.
Também gera a lista `tags` a partir das palavras-chave.

Uso:
    .venv/bin/python scripts/extrair_resumos_repositorios.py --limit 10
    .venv/bin/python scripts/extrair_resumos_repositorios.py
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
CACHE = ROOT / ".cache" / "resumos"
REPORT = ROOT / "dados" / "resumos.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
session = requests.Session()
session.headers.update(HEADERS)


def clean(value) -> str:
    text = str(value or "").replace("\xa0", " ")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def cache_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / f"{digest}.html"


BLOCKED_DOMAINS = (
    "tede2.pucsp.br",
    "repositorio.pgsscogna.com.br",
    "repositorio.cruzeirodosul.edu.br",
)


def fetch(url: str, force: bool = False) -> str:
    if any(domain in url for domain in BLOCKED_DOMAINS):
        return ""
    path = cache_path(url)
    if path.exists() and not force:
        return path.read_text(encoding="utf-8", errors="ignore")
    for attempt in range(2):
        try:
            response = session.get(url, timeout=15, allow_redirects=True)
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


def extract_abstract(html: str) -> tuple[str, str]:
    """Retorna (resumo, idioma)."""
    if not html:
        return "", ""
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").lower()
        if name not in ("dc.description", "dcterms.abstract", "citation_abstract", "description"):
            continue
        content = clean(meta.get("content") or "")
        if len(content) < 120:
            continue
        if content.lower().startswith(("http://", "https://")):
            continue
        language = (meta.get("xml:lang") or "").lower()
        candidates.append((content, language))

    if not candidates:
        # Alguns repositórios usam <div class="abstract"> ou <blockquote class="abstract">.
        for element in soup.select(".abstract, .resumo, .item-abstract, blockquote.abstract"):
            content = clean(element.get_text(" "))
            if len(content) >= 120:
                candidates.append((content, ""))

    if not candidates:
        return "", ""

    # Prefere português; depois o maior texto.
    def score(pair):
        content, language = pair
        return (1 if language.startswith("por") else 0, len(content))

    content, language = max(candidates, key=score)
    if not language:
        portuguese = re.search(
            r"\b(este|esta|esse|essa|trabalho|pesquisa|objetivo|investiga|análise|resultados)\b",
            content.lower(),
        )
        language = "por" if portuguese else "eng"
    return content, language


def make_tags(item: dict) -> list[str]:
    sources = []
    bdtd = clean(item.get("palavras_chave_bdtd", ""))
    original = clean(item.get("palavras_chave", ""))
    if bdtd:
        sources = [part.strip() for part in re.split(r"[;]", bdtd)]
    elif original:
        sources = [part.strip() for part in re.split(r"[;,.]", original)]
    tags = []
    seen = set()
    for tag in sources:
        tag = re.sub(r"^[\s\-–•]+|[\s.;,]+$", "", tag)
        tag = re.sub(r"\s+", " ", tag)
        if not tag or len(tag) < 2:
            continue
        if tag.isupper() and len(tag.split()) >= 3:
            continue
        key = tag.lower()
        if key in seen or key.startswith("cnpq::") or tag.lower() == "não possui palavras-chave":
            continue
        parts = re.split(r"\s+e\s+", tag)
        if len(parts) == 2 and parts[1][:1].isupper() and len(parts[1].split()) >= 2:
            for part in parts:
                part_key = part.lower()
                if part_key not in seen:
                    seen.add(part_key)
                    tags.append(part.strip())
            continue
        seen.add(key)
        tags.append(tag)
    return tags[:20]


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
    if args.limit:
        files = files[: args.limit]

    report = []
    for position, path in enumerate(files, start=1):
        item = json.loads(path.read_text(encoding="utf-8"))
        links = item.get("links", {})
        item["tags"] = make_tags(item)

        url = links.get("registro_institucional") or ""
        if url and (args.force or not item.get("resumo")):
            print(f"[{position}/{len(files)}] {item['id']} — {url}", flush=True)
            html = fetch(url, force=args.force)
            abstract, language = extract_abstract(html)
            if abstract:
                item["resumo"] = abstract
                item["resumo_idioma"] = language
                item["resumo_fonte"] = url
                print(f"  → resumo {len(abstract)} caracteres ({language})", flush=True)
                report.append({"id": item["id"], "status": "ok", "chars": len(abstract), "url": url})
            else:
                print("  → sem resumo extraível", flush=True)
                report.append({"id": item["id"], "status": "sem_resumo", "url": url})
        else:
            report.append(
                {
                    "id": item["id"],
                    "status": "mantido" if item.get("resumo") else "sem_link",
                    "chars": len(item.get("resumo", "")),
                }
            )

        path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = sum(1 for entry in report if entry.get("status") == "ok")
    print(f"\n✓ {ok} resumos extraídos")


if __name__ == "__main__":
    main()
