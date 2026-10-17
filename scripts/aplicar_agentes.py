#!/usr/bin/env python3
"""
Aplica os resultados de pesquisa dos agentes (JSON) às fichas.

Uso:
    python scripts/aplicar_agentes.py dados/resultado_agentes_1.json [...]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "site/public/data/itens"


def is_url(value) -> bool:
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def is_full_name(value: str) -> bool:
    words = re.sub(r"\s+", " ", str(value or "")).strip().split()
    return len(words) >= 2 and sum(1 for word in words if len(word) > 2) >= 2


def main() -> None:
    files = [Path(value) for value in sys.argv[1:]]
    if not files:
        print("Informe ao menos um arquivo JSON de resultados.")
        return

    changed = 0
    report = []
    for source in files:
        data = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = [data]
        for result in data:
            item_id = result.get("id")
            path = ITEMS / f"{item_id}.json"
            if not path.exists():
                report.append({"id": item_id, "status": "arquivo_nao_encontrado"})
                continue
            item = json.loads(path.read_text(encoding="utf-8"))
            found = bool(result.get("encontrado"))
            confidence = str(result.get("confianca", "")).lower()
            if not found or confidence == "baixa":
                report.append({"id": item_id, "status": "ignorado", "confianca": confidence})
                continue

            item["autor_planilha"] = item.get("autor_planilha") or item.get("autor", "")
            item["orientador_planilha"] = item.get("orientador_planilha") or item.get("orientador", "")

            author = result.get("autor") or ""
            if is_full_name(author) and confidence in ("alta", "media"):
                item["autor"] = author

            advisor = result.get("orientador") or ""
            if is_full_name(advisor) and confidence in ("alta", "media"):
                item["orientador"] = advisor

            year = result.get("ano")
            try:
                year = int(year)
                if 1980 <= year <= 2025:
                    item["ano"] = year
            except (TypeError, ValueError):
                pass

            degree = str(result.get("grau") or "")
            if "doutor" in degree.lower():
                item["grau"] = "Doutorado"
                item["tipo"] = "Tese"
            elif "profissional" in degree.lower():
                item["grau"] = "Mestrado Profissional"
                item["tipo"] = "Dissertação"
            elif "mestrado" in degree.lower():
                item["grau"] = "Mestrado Acadêmico"
                item["tipo"] = "Dissertação"

            if result.get("instituicao"):
                item["instituicao_agente"] = result["instituicao"]
            if result.get("programa"):
                item["programa_agente"] = result["programa"]

            links = item.setdefault("links", {})
            if is_url(result.get("link_texto_completo")):
                links["texto_completo"] = result["link_texto_completo"]
            if is_url(result.get("link_registro")):
                links["registro_institucional"] = result["link_registro"]

            item["enriquecimento_manual"] = {
                "fonte": result.get("fonte", ""),
                "confianca": confidence,
                "observacao": result.get("observacao", ""),
            }

            path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1
            report.append(
                {
                    "id": item_id,
                    "status": "aplicado",
                    "autor": item.get("autor"),
                    "orientador": item.get("orientador"),
                    "link": links.get("texto_completo") or links.get("registro_institucional"),
                }
            )

    out = ROOT / "dados" / "aplicacao_agentes.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✓ {changed} fichas atualizadas")
    print(f"  relatório: {out}")


if __name__ == "__main__":
    main()
