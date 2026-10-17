#!/usr/bin/env python3
"""Normaliza resumos, tags e links depois do enriquecimento BDTD/repositórios."""

from __future__ import annotations

import glob
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "site/public/data/itens"
BAD_ABSTRACT = re.compile(r"^(orientador|dissertação|tese|não informado|resumo)\b", re.I)


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.lower()).strip()


def normalize_tags(values) -> list[str]:
    tags = []
    seen = set()
    for value in values or []:
        word = clean(value).strip(" .,;:-")
        if not word or word.lower().startswith("cnpq::") or len(word) > 120:
            continue
        key = norm(word)
        if key in seen:
            continue
        seen.add(key)
        tags.append(word)
    return tags[:24]


def valid_abstract(text: str) -> bool:
    text = clean(text)
    return len(text) >= 150 and not BAD_ABSTRACT.match(text)


def main() -> None:
    changed = 0
    for path in sorted(glob.glob(str(ITEMS / "*.json"))):
        item = json.loads(Path(path).read_text(encoding="utf-8"))
        before = json.dumps(item, ensure_ascii=False, sort_keys=True)

        resumo = clean(item.get("resumo"))
        if resumo and not valid_abstract(resumo):
            item["resumo"] = ""
            item["resumo_idioma"] = ""
            item["resumo_fonte"] = ""

        resumo_bdtd = clean(item.get("resumo_bdtd"))
        if resumo_bdtd and not valid_abstract(resumo_bdtd):
            item["resumo_bdtd"] = ""

        item["tags"] = normalize_tags(item.get("tags"))

        links = item.setdefault("links", {})
        full = clean(links.get("texto_completo"))
        registro = clean(links.get("registro_institucional"))
        if full and full == registro and not re.search(r"\.pdf(?:$|\?)", full, re.I):
            # Um handle de repositório não é o PDF; permanece como registro.
            links.pop("texto_completo", None)

        after = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if before != after:
            Path(path).write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1

    print(f"✓ {changed} fichas normalizadas")


if __name__ == "__main__":
    main()
