#!/usr/bin/env python3
"""Extrai o resumo em português do campo `spelling` dos registros BDTD."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "site/public/data/itens"
CACHE = ROOT / ".cache" / "bdtd-spelling"
CACHE.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept-Language": "pt-BR,pt;q=0.9"}
session = requests.Session()
session.headers.update(HEADERS)

START = re.compile(
    r"(Este trabalho|Esta pesquisa|Esta tese|Esta dissertação|"
    r"O objetivo|O presente|A presente|Neste trabalho|Nesta pesquisa|"
    r"O estudo|Este estudo|A pesquisa|A investigação|O ensino|"
    r"Buscou-se|Procuramos|Investigamos|Apresentamos)\b"
)
END = re.compile(r"(info:eu-repo|reponame:|porreponame|TEDE|https?://|This work|This study|The objective)\b")


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def valid(text: str) -> bool:
    text = clean(text)
    if len(text) < 300:
        return False
    if text.lower().startswith(("orientador", "dissertação", "tese", "não informado", "resumo:")):
        return False
    portuguese = len(re.findall(r"\b(este|esta|trabalho|pesquisa|objetivo|investiga|análise|resultados|ensino|alunos|professores|dados)\b", text.lower()))
    return portuguese >= 2


def extract(spelling: str) -> str:
    text = clean(spelling)
    matches = list(START.finditer(text))
    if not matches:
        return ""
    # Prefere o último marcador que ainda deixa um trecho longo (o citation pode ter "O objetivo").
    for match in reversed(matches):
        start = match.start()
        tail = text[start:]
        end = END.search(tail[20:])
        if end:
            tail = tail[: 20 + end.start()]
        tail = clean(tail)
        if valid(tail):
            return tail
    return ""


def fetch(url: str) -> str:
    path = CACHE / f"{hashlib.sha1(url.encode()).hexdigest()}.html"
    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")
    for attempt in range(3):
        try:
            response = session.get(url, timeout=25)
            if response.status_code == 200:
                path.write_text(response.text, encoding="utf-8")
                time.sleep(0.5)
                return response.text
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(3 * (attempt + 1))
                continue
            return ""
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    files = sorted(ITEMS.glob("*.json"))
    if args.only:
        only = {value.strip() for value in args.only.split(",") if value.strip()}
        files = [path for path in files if path.stem in only]
    changed = 0
    for position, path in enumerate(files, start=1):
        item = json.loads(path.read_text(encoding="utf-8"))
        current = clean(item.get("resumo"))
        if item.get("resumo_idioma") in ("por", "pt", "pt_br") and valid(current) and not args.force:
            continue
        url = item.get("links", {}).get("bdtd_registro") or ""
        if not url:
            continue
        print(f"[{position}/{len(files)}] {item['id']}", flush=True)
        html = fetch(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        spelling = ""
        for th in soup.find_all("th"):
            if clean(th.get_text(" ")) == "spelling":
                cell = th.find_next_sibling("td")
                spelling = cell.get_text(" ", strip=True) if cell else ""
                break
        abstract = extract(spelling)
        if abstract and (args.force or item.get("resumo_idioma") not in ("por", "pt", "pt_br") or len(abstract) > len(current)):
            item["resumo"] = abstract
            item["resumo_idioma"] = "por"
            item["resumo_fonte"] = url
            path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1
            print(f"  → {len(abstract)} caracteres", flush=True)
    print(f"✓ {changed} resumos em português extraídos do campo spelling")


if __name__ == "__main__":
    main()
