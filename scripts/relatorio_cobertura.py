#!/usr/bin/env python3
"""Gera um relatório de cobertura BDTD/resumo/tags por registro."""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "site/public/data/itens"
OUT = ROOT / "dados" / "cobertura_bdtd.json"


def has_abstract(item: dict) -> bool:
    text = (item.get("resumo") or "").strip()
    if len(text) < 150:
        return False
    return not re.match(r"^(orientador|dissertação|tese|não informado|resumo)\b", text, re.I)


def main() -> None:
    rows = []
    for path in sorted(glob.glob(str(ITEMS / "*.json"))):
        item = json.loads(Path(path).read_text(encoding="utf-8"))
        links = item.get("links", {})
        rows.append(
            {
                "id": item["id"],
                "titulo": item.get("titulo", ""),
                "instituicao": item.get("instituicao", ""),
                "bdtd_url": links.get("bdtd_registro") or "",
                "repositorio_url": links.get("registro_institucional") or links.get("texto_completo") or "",
                "resumo_pt": has_abstract(item) and item.get("resumo_idioma") in ("por", "pt", "pt_br"),
                "resumo_fonte": item.get("resumo_fonte") or "",
                "tags_pt": bool(item.get("tags")),
                "thumbnail": item.get("thumbnail", ""),
            }
        )
    totals = {
        "total": len(rows),
        "bdtd": sum(bool(row["bdtd_url"]) for row in rows),
        "resumo_pt": sum(bool(row["resumo_pt"]) for row in rows),
        "repositorio": sum(bool(row["repositorio_url"]) for row in rows),
        "tags_pt": sum(bool(row["tags_pt"]) for row in rows),
        "thumbnail": sum(bool(row["thumbnail"]) for row in rows),
    }
    OUT.write_text(json.dumps({"totais": totals, "registros": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(totals, ensure_ascii=False))


if __name__ == "__main__":
    main()
