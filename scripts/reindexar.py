#!/usr/bin/env python3
"""
Reconstrói indice.json e agregados.json a partir das fichas enriquecidas.
Use depois de enriquecer_capes.py / enriquecer_bdtd.py.

Uso: .venv/bin/python scripts/reindexar.py
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "site/public/data/itens"
INDEX = ROOT / "site/public/data/indice.json"
AGREGADOS = ROOT / "site/public/data/agregados.json"

AREAS = [
    "Educação Matemática",
    "Ensino de Matemática",
    "Ensino de Ciências e Matemática",
    "Educação",
    "Estatística e Matemática",
    "Engenharia",
    "Psicologia",
    "Computação",
    "Administração",
    "Ensino",
    "Outros",
]
REGIOES = ["Sudeste", "Sul", "Nordeste", "Centro-Oeste", "Norte"]
GRAUS = ["Mestrado Acadêmico", "Mestrado Profissional", "Doutorado", "Doutorado Profissional"]
TIPOS = ["Dissertação", "Tese"]
CONTEUDOS = [
    "Estatística",
    "Probabilidade",
    "Combinatória",
    "Probabilidade e Estatística",
    "Combinatória e Probabilidade",
    "Combinatória, Probabilidade e Estatística",
]


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.lower()).strip()


def main() -> None:
    items = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(ITEMS.glob("*.json"))]
    items.sort(key=lambda item: item["id"])

    index = []
    for item in items:
        links = item.get("links", {})
        link = (
            links.get("texto_completo")
            or links.get("registro_institucional")
            or links.get("bdtd_registro")
            or links.get("capes")
            or ""
        )
        resumo = clean(
            item.get("resumo") or item.get("resumo_bdtd") or item.get("problema") or ""
        )
        parts = [
            item.get("titulo", ""),
            item.get("autor", ""),
            item.get("autor_planilha", ""),
            item.get("instituicao", ""),
            item.get("instituicao_capes", ""),
            item.get("orientador", ""),
            item.get("programa", ""),
            item.get("programa_capes", ""),
            item.get("area", ""),
            item.get("nivel", ""),
            item.get("foco", ""),
            item.get("conteudo", ""),
            item.get("palavras_chave", ""),
            item.get("palavras_chave_bdtd", ""),
            resumo,
            item.get("resumo_bdtd", ""),
            item.get("resumo", ""),
            " ".join(item.get("tags", [])),
        ]
        busca = clean(" ".join(str(part) for part in parts if part)).lower()

        index.append(
            {
                "id": item["id"],
                "thumbnail": item.get("thumbnail", ""),
                "autor": item.get("autor", ""),
                "autor_planilha": item.get("autor_planilha", ""),
                "ano": item.get("ano"),
                "tipo": item.get("tipo", ""),
                "titulo": item.get("titulo", ""),
                "instituicao": item.get("instituicao", ""),
                "instituicao_capes": item.get("instituicao_capes", ""),
                "cidade": item.get("cidade", ""),
                "estado": item.get("estado", ""),
                "regiao": item.get("regiao", ""),
                "orientador": item.get("orientador", ""),
                "programa": item.get("programa", ""),
                "programa_capes": item.get("programa_capes", ""),
                "area": item.get("area", ""),
                "nivel": item.get("nivel", ""),
                "foco": item.get("foco", ""),
                "grau": item.get("grau", ""),
                "conteudo": item.get("conteudo", ""),
                "resumo": resumo[:360],
                "palavras_chave": item.get("palavras_chave", ""),
                "palavras_chave_bdtd": item.get("palavras_chave_bdtd", ""),
                "resumo_bdtd": item.get("resumo_bdtd", ""),
                "tags": item.get("tags", []),
                "link": link,
                "bdtd_url": links.get("bdtd_registro", ""),
                "busca": busca,
                "busca_norm": norm(busca),
            }
        )

    INDEX.write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )

    by_year = Counter(item.get("ano") for item in index if item.get("ano"))
    by_grau = Counter(item.get("grau") for item in index)
    by_tipo = Counter(item.get("tipo") for item in index)
    by_regiao = Counter(item.get("regiao") for item in index)
    by_estado = Counter(item.get("estado") for item in index)
    by_area = Counter(item.get("area") for item in index)
    by_foco = Counter(item.get("foco") for item in index)
    by_conteudo = Counter(item.get("conteudo") for item in index)
    by_nivel = Counter(item.get("nivel") for item in index)
    by_instituicao = Counter(item.get("instituicao") for item in index)

    def series(counter: Counter, keys=None, label="total"):
        keys = keys if keys is not None else [key for key, _ in counter.most_common()]
        return [{("ano" if label == "ano" else "rotulo"): key, label: counter.get(key, 0)} for key in keys]

    agregados = {
        "total": len(index),
        "periodo": {"inicio": 1984, "fim": 2024},
        "instituicoes": len([value for value in by_instituicao if value]),
        "estados": len([value for value in by_estado if value]),
        "regioes": len([value for value in by_regiao if value]),
        "atualizado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "por_ano": [{"ano": year, "total": by_year.get(year, 0)} for year in range(1984, 2025)],
        "por_grau": series(by_grau, GRAUS),
        "por_tipo": series(by_tipo, TIPOS),
        "por_regiao": series(by_regiao, REGIOES),
        "por_estado": series(by_estado),
        "por_area": series(by_area, AREAS),
        "por_foco": series(by_foco),
        "por_conteudo": series(by_conteudo, CONTEUDOS),
        "por_nivel": series(by_nivel),
        "top_instituicoes": [
            {"nome": name, "total": total}
            for name, total in by_instituicao.most_common(12)
            if name and name.strip()
        ],
    }
    AGREGADOS.write_text(json.dumps(agregados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✓ {len(index)} registros reindexados; agregados recalculados")


if __name__ == "__main__":
    main()
