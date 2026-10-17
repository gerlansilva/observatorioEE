#!/usr/bin/env python3
"""Aplica os resultados dos agentes de links BDTD/repositórios."""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path

from aplicar_agentes_pt import is_english, valid_abstract, valid_url

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "site/public/data/itens"
RESULTS = ROOT / "dados" / "agentes"


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def main() -> None:
    applied = rejected = 0
    report = []
    for file in sorted(glob.glob(str(RESULTS / "links_result*.json"))):
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
                continue
            item = json.loads(path.read_text(encoding="utf-8"))
            confidence = clean(entry.get("confianca")).lower()
            if confidence == "baixa":
                rejected += 1
                report.append({"id": item_id, "status": "confianca_baixa"})
                continue

            links = item.setdefault("links", {})
            bdtd_url = clean(entry.get("bdtd_url"))
            repo_url = clean(entry.get("repositorio_url"))
            resumo = clean(entry.get("resumo_pt"))
            source = clean(entry.get("fonte_resumo"))
            tags = entry.get("palavras_chave_pt") or []
            if not isinstance(tags, list):
                tags = []
            tags = [clean(tag) for tag in tags if clean(tag) and not is_english(tag)]

            changed = False
            if valid_url(bdtd_url, bdtd=True):
                links["bdtd_registro"] = bdtd_url
                item["bdtd_registro"] = {
                    "status": "ok",
                    "id": bdtd_url.rstrip("/").rsplit("/", 1)[-1],
                    "url": bdtd_url,
                    "fonte": "agente",
                }
                changed = True
            if valid_url(repo_url):
                if repo_url.lower().endswith(".pdf"):
                    links["texto_completo"] = repo_url
                else:
                    links["registro_institucional"] = repo_url
                changed = True
            if resumo and valid_abstract(resumo) and valid_url(source):
                existing_pt = item.get("resumo_idioma") in ("por", "pt", "pt_br") and item.get("resumo")
                if not existing_pt or len(resumo) > len(item.get("resumo", "")):
                    item["resumo"] = resumo
                    item["resumo_idioma"] = "por"
                    item["resumo_fonte"] = source
                    changed = True
            if tags:
                existing = [tag for tag in item.get("tags", []) if not is_english(tag)]
                merged = []
                seen = set()
                for tag in [*tags, *existing]:
                    key = tag.lower()
                    if key not in seen:
                        seen.add(key)
                        merged.append(tag)
                item["tags"] = merged[:24]
                changed = True

            if not changed:
                rejected += 1
                report.append({"id": item_id, "status": "sem_dados_validos"})
                continue
            item["pesquisa_agente_links"] = {
                "status": "ok",
                "fonte_resumo": source or None,
                "fonte_palavras": clean(entry.get("fonte_palavras")) or None,
                "confianca": confidence or "media",
            }
            path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            applied += 1
            report.append({"id": item_id, "status": "aplicado", "bdtd": bool(bdtd_url), "repo": bool(repo_url), "resumo": bool(resumo), "tags": len(tags)})

    (RESULTS / "aplicacao_links.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✓ {applied} fichas atualizadas; {rejected} resultados recusados")


if __name__ == "__main__":
    main()
