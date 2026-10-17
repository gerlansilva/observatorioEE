#!/usr/bin/env python3
"""
Converte nomes no formato de citação ("SILVA, G.") para a ordem natural
("G. Silva") quando a CAPES/BDTD não localizou o nome completo.
Execute antes de reindexar.py.

Uso: .venv/bin/python scripts/normalizar_nomes.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "site/public/data/itens"
LOWER = {"de", "da", "do", "das", "dos", "e"}


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def smart_case(value: str) -> str:
    text = clean(value).lower()
    if not text:
        return ""
    result = []
    for index, word in enumerate(text.split()):
        if index > 0 and word in LOWER:
            result.append(word)
        else:
            result.append(word[:1].upper() + word[1:])
    return " ".join(result)


def natural(value: str) -> str:
    text = clean(value)
    if not text:
        return ""
    if "," in text:
        parts = [part.strip() for part in text.split(",") if part.strip()]
        if len(parts) >= 2:
            result = " ".join([parts[1], parts[0], *parts[2:]])
            return smart_case(result) if text.isupper() else result
    if text.isupper():
        return smart_case(text)
    return text


def main() -> None:
    changed = 0
    for path in sorted(ITEMS.glob("*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        updates = {}
        if item.get("autor") and "," in item["autor"]:
            updates["autor_planilha"] = item.get("autor_planilha") or item["autor"]
            updates["autor"] = natural(item["autor"])
        elif item.get("autor") and item["autor"].isupper():
            updates["autor"] = natural(item["autor"])
        if item.get("orientador") and "," in item["orientador"]:
            updates["orientador_planilha"] = item.get("orientador_planilha") or item["orientador"]
            updates["orientador"] = natural(item["orientador"])
        elif item.get("orientador") and item["orientador"].isupper():
            updates["orientador"] = natural(item["orientador"])
        if updates:
            item.update(updates)
            path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1
    print(f"✓ {changed} fichas com nomes normalizados")


if __name__ == "__main__":
    main()
