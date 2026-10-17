#!/usr/bin/env python3
"""
Gera o CSV público a partir das fichas enriquecidas em site/public/data/itens.

Uso: .venv/bin/python scripts/exportar_csv.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "site/public/data/itens"
CSV_OUT = ROOT / "dados/teses.csv"
PUBLIC_CSV = ROOT / "site/public/dados/teses.csv"

FIELDS = [
    "id",
    "autor",
    "autor_planilha",
    "autor_capes",
    "ano",
    "tipo",
    "titulo",
    "instituicao",
    "instituicao_capes",
    "cidade",
    "cidade_capes",
    "estado",
    "regiao",
    "orientador",
    "orientador_planilha",
    "orientador_capes",
    "programa",
    "programa_capes",
    "area",
    "nivel",
    "foco",
    "grau",
    "conteudo",
    "problema",
    "metodologia",
    "contribuicoes",
    "palavras_chave",
    "palavras_chave_bdtd",
    "referencial",
    "resumo_bdtd",
    "resumo",
    "resumo_idioma",
    "resumo_fonte",
    "tags",
    "links",
    "capes_url",
    "bdtd_url",
    "enriquecimento",
]


def main() -> None:
    rows = []
    for path in sorted(ITEMS.glob("*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        row = {field: item.get(field, "") for field in FIELDS}
        links = item.get("links", {})
        row["links"] = json.dumps(links, ensure_ascii=False)
        row["tags"] = json.dumps(item.get("tags", []), ensure_ascii=False)
        row["capes_url"] = links.get("capes", "")
        row["bdtd_url"] = links.get("bdtd_registro", "")
        row["enriquecimento"] = json.dumps(
            {
                "capes": item.get("capes", {}),
                "bdtd": item.get("bdtd", {}),
            },
            ensure_ascii=False,
        )
        rows.append(row)

    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_CSV.parent.mkdir(parents=True, exist_ok=True)
    for destination in (CSV_OUT, PUBLIC_CSV):
        with destination.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    print(f"✓ CSV gerado com {len(rows)} registros: {CSV_OUT}")
    print(f"  cópia pública: {PUBLIC_CSV}")


if __name__ == "__main__":
    main()
