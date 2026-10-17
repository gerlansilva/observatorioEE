#!/usr/bin/env python3
"""Aplica os resultados de pesquisa dos agentes (resumo PT, tags PT, link BDTD)."""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "site/public/data/itens"
RESULTS = ROOT / "dados" / "agentes"

ENGLISH = {
    "the", "and", "of", "in", "to", "for", "with", "on", "by", "from", "as",
    "teaching", "learning", "education", "statistics", "statistical", "probability",
    "mathematics", "mathematical", "students", "teachers", "school", "research",
    "study", "analysis", "data", "quality", "evaluation", "assessment", "attitudes",
    "affectivity", "combinatorics", "computer", "software", "distance", "formation",
    "knowledge", "paradigms", "inference", "randomness", "reality", "determinism",
    "project", "works", "higher", "elementary", "pedagogy", "practice", "development",
}


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def is_english(text: str) -> bool:
    lowered = clean(text).lower()
    if re.search(r"\b(of|and|the|in|for|with)\b", lowered):
        return True
    words = re.findall(r"[a-zà-ÿ’'-]+", lowered)
    if not words:
        return False
    return sum(1 for word in words if word.strip("’'") in ENGLISH) >= max(1, len(words) // 2)


def valid_abstract(text: str) -> bool:
    text = clean(text)
    if len(text) < 300:
        return False
    if text.lower().startswith(("orientador", "dissertação", "tese", "não informado", "resumo:")):
        return False
    portuguese = len(
        re.findall(
            r"\b(este|esta|esse|essa|estudo|trabalho|pesquisa|objetivo|investiga|investigou|análise|analisou|resultados|ensino|aprendizagem|alunos|professores|dados|foram|utilizados|conclusão|presente|leitura|gráficos|estatística)\b",
            text.lower(),
        )
    )
    return (portuguese >= 2 or (portuguese >= 1 and re.search(r"[ãõçáéíóúâêô]", text, re.I))) and not is_english(text)


def valid_url(url: str, bdtd: bool = False) -> bool:
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return False
    if bdtd:
        return "bdtd.ibict.br/vufind/Record/" in url
    return True


def main() -> None:
    files = sorted(
        glob.glob(str(RESULTS / "abstract_pt_result*.json"))
        + glob.glob(str(RESULTS / "abstract_bdtd_result*.json"))
    )
    applied = rejected = 0
    report = []
    for file in files:
        try:
            data = json.loads(Path(file).read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            print(f"! {file}: JSON inválido ({error})")
            continue
        if not isinstance(data, list):
            continue
        for entry in data:
            item_id = clean(entry.get("id"))
            path = ITEMS / f"{item_id}.json"
            if not item_id or not path.exists():
                rejected += 1
                report.append({"id": item_id, "status": "id_inexistente"})
                continue
            item = json.loads(path.read_text(encoding="utf-8"))
            resumo = clean(entry.get("resumo_pt"))
            source = clean(entry.get("fonte_resumo"))
            tags = entry.get("palavras_chave_pt") or []
            if not isinstance(tags, list):
                tags = []
            tags = [clean(tag) for tag in tags if clean(tag) and not is_english(tag)]
            bdtd_url = clean(entry.get("bdtd_url"))
            confidence = clean(entry.get("confianca")).lower()

            if resumo and not valid_abstract(resumo):
                rejected += 1
                report.append({"id": item_id, "status": "resumo_invalido", "chars": len(resumo)})
                continue
            if resumo and not valid_url(source):
                rejected += 1
                report.append({"id": item_id, "status": "fonte_invalida", "fonte": source})
                continue
            if not resumo and not tags and not valid_url(bdtd_url, bdtd=True):
                rejected += 1
                report.append({"id": item_id, "status": "sem_dados_validos"})
                continue
            if confidence == "baixa":
                rejected += 1
                report.append({"id": item_id, "status": "confianca_baixa"})
                continue

            links = item.setdefault("links", {})
            if resumo:
                item["resumo"] = resumo
                item["resumo_idioma"] = "por"
                item["resumo_fonte"] = source
            if tags:
                existing = item.get("tags", [])
                merged = []
                seen = set()
                for tag in [*tags, *existing]:
                    key = tag.lower()
                    if key not in seen and not is_english(tag):
                        seen.add(key)
                        merged.append(tag)
                item["tags"] = merged[:24]
            if valid_url(bdtd_url, bdtd=True):
                links["bdtd_registro"] = bdtd_url
                item["bdtd_registro"] = {
                    "status": "ok",
                    "id": bdtd_url.rstrip("/").rsplit("/", 1)[-1],
                    "url": bdtd_url,
                    "fonte": "agente",
                }

            item["pesquisa_agente"] = {
                "status": "ok",
                "fonte_resumo": source or None,
                "fonte_palavras": clean(entry.get("fonte_palavras")) or None,
                "confianca": confidence or "media",
            }
            path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            applied += 1
            report.append({"id": item_id, "status": "aplicado", "resumo": bool(resumo), "tags": len(tags), "bdtd": bool(bdtd_url)})

    (RESULTS / "aplicacao.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✓ {applied} fichas atualizadas; {rejected} resultados recusados")


if __name__ == "__main__":
    main()
