#!/usr/bin/env python3
"""Remove metadados de repositório que vazaram para o fim de alguns resumos."""

from __future__ import annotations

import glob
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "site/public/data/itens"

PATTERNS = [
    r"\b\d{1,4}\s*(?:f\.|p\.)",
    r"application/pdf",
    r"Disponível em formato digital",
    r"\binfo:eu-repo\b",
    r"\breponame:",
    r"\bpor(?:Florianópolis|São Paulo|Rio de Janeiro|Porto Alegre|Salvador|Recife|Belo Horizonte|Curitiba|Campinas|São Carlos|Bauru|Araraquara|Marília|Presidente Prudente)",
]


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.lower()).strip()


def main() -> None:
    changed = 0
    for path in sorted(glob.glob(str(ITEMS / "*.json"))):
        item = json.loads(Path(path).read_text(encoding="utf-8"))
        text = clean(item.get("resumo"))
        if len(text) < 300:
            continue
        original = text
        tail_start = 200

        cuts = []
        for pattern in PATTERNS:
            for match in re.finditer(pattern, text, re.I):
                if match.start() >= tail_start:
                    cuts.append(match.start())
                    break
        if cuts:
            text = text[: min(cuts)]

        text = clean(text)
        if text != original and len(text) >= 300:
            item["resumo"] = text
            Path(path).write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1
            print(f"{item['id']}: {len(original)} → {len(text)}")

    print(f"✓ {changed} resumos limpos")


if __name__ == "__main__":
    main()
