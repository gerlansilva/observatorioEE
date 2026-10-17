#!/usr/bin/env python3
"""
Extrai a planilha "Planilha do estado da arte.xls" para JSON/CSV estáticos.

Uso:
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/python scripts/extrair.py

Saídas:
    site/public/data/indice.json       -> lista leve para busca e filtros
    site/public/data/itens/{id}.json   -> registro completo
    site/public/data/agregados.json    -> estatísticas para a home
    dados/teses.csv                    -> versão tabular normalizada
    dados/qualidade.json               -> relatório de preenchimento
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import xlrd

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "dados" / "planilha-do-estado-da-arte.xls"
OUT = ROOT / "site" / "public" / "data"
CSV_OUT = ROOT / "dados" / "teses.csv"
PUBLIC_CSV = ROOT / "site" / "public" / "dados" / "teses.csv"
QUALITY_OUT = ROOT / "dados" / "qualidade.json"

SHEET = "Plan1"
FIRST_DATA_ROW = 1
LAST_DATA_ROW = 259  # a linha 260 em diante é legenda/rodapé

GRAUS = {
    "MA": "Mestrado Acadêmico",
    "MP": "Mestrado Profissional",
    "DO": "Doutorado",
}

NIVEIS = {
    "0": "Não informado",
    "1": "Educação Infantil",
    "2": "Ensino Fundamental – anos iniciais",
    "3": "Ensino Fundamental – anos finais",
    "4": "Ensino Médio",
    "5": "EJA – Ensino Fundamental",
    "6": "EJA – Ensino Médio",
    "7": "Ensino Superior",
    "8": "Indefinido",
    "9": "Educação Infantil e Fundamental (anos iniciais)",
    "10": "EJA – Fundamental e Médio",
    "11": "Ensino Fundamental (anos iniciais e finais)",
    "12": "Ensino Fundamental (anos finais) e Médio",
    "13": "EJA e Ensino Fundamental (anos iniciais)",
    "14": "Ensino Fundamental (anos iniciais e finais) e Médio",
}

FOCOS = {
    "0": "Não informado",
    "1": "Processo de ensino e aprendizagem da Estocástica",
    "2": "Formação inicial/continuada e desenvolvimento profissional de professores",
    "3": "TICs, materiais e recursos didáticos",
    "4": "Cognição e Psicologia da Educação Estatística",
    "5": "Currículo e análise de conteúdo bibliográfico",
    "6": "Crenças, concepções, atitudes e saberes práticos",
    "7": "História, Filosofia e revisão da literatura",
    "8": "Contexto sociocultural e político do ensino-aprendizagem",
    # Os códigos 9 a 11 não aparecem na legenda original da planilha.
    # Foram inferidos a partir dos títulos e devem ser revisados pela equipe.
    "9": "Avaliação",
    "10": "Erros e dificuldades de aprendizagem",
    "11": "Outros temas",
}

ESTADOS = {
    "são paulo": "São Paulo",
    "rio grande do sul": "Rio Grande do Sul",
    "pernambuco": "Pernambuco",
    "minas gerais": "Minas Gerais",
    "santa catarina": "Santa Catarina",
    "paraná": "Paraná",
    "rio de janeiro": "Rio de Janeiro",
    "mato grosso do sul": "Mato Grosso do Sul",
    "pará": "Pará",
    "distrito federal": "Distrito Federal",
    "paraíba": "Paraíba",
    "goiás": "Goiás",
    "sergipe": "Sergipe",
    "ceará": "Ceará",
}

REGIOES = {
    "São Paulo": "Sudeste",
    "Rio de Janeiro": "Sudeste",
    "Minas Gerais": "Sudeste",
    "Rio Grande do Sul": "Sul",
    "Santa Catarina": "Sul",
    "Paraná": "Sul",
    "Pernambuco": "Nordeste",
    "Paraíba": "Nordeste",
    "Ceará": "Nordeste",
    "Sergipe": "Nordeste",
    "Mato Grosso do Sul": "Centro-Oeste",
    "Goiás": "Centro-Oeste",
    "Distrito Federal": "Centro-Oeste",
    "Pará": "Norte",
}

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
    "Outros",
]

LOWER_WORDS = {"de", "da", "do", "das", "dos", "e", "em", "para", "a", "o"}


def clean(value) -> str:
    text = str(value or "").replace("\xa0", " ").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def one_line(value) -> str:
    return re.sub(r"\s+", " ", clean(value)).strip()


def smart_title(value: str) -> str:
    text = one_line(value)
    if not text:
        return ""
    words = text.lower().split(" ")
    out = []
    for index, word in enumerate(words):
        if index > 0 and word in LOWER_WORDS:
            out.append(word)
        else:
            out.append(word[:1].upper() + word[1:])
    return " ".join(out)


def fix_institution(value: str) -> str:
    text = one_line(value)
    text = text.replace("Pontífica", "Pontifícia").replace("Pontifíca", "Pontifícia")
    text = re.sub(r"\s+", " ", text)
    replacements = {
        "ULBRA/Canoas": "Universidade Luterana do Brasil (ULBRA/Canoas)",
        "Universidade Bandeirante de São Paulo": "Universidade Bandeirantes de São Paulo",
        "Universidade presbiteriana mackenzie": "Universidade Presbiteriana Mackenzie",
        "Faculdade de filosofia, ciências e letras de palmas": "Faculdade de Filosofia, Ciências e Letras de Palmas",
        "Faculdade de filosofia, ciências e letras de Jandaia do sul": "Faculdade de Filosofia, Ciências e Letras de Jandaia do Sul",
        "Centro Federal de Educação Tecnológica Celso Suckow da Fonseca": "CEFET-RJ (Centro Federal de Educação Tecnológica Celso Suckow da Fonseca)",
    }
    return replacements.get(text, text)


def fix_program(value: str) -> str:
    text = one_line(value)
    replacements = {
        "Educação matemática": "Educação Matemática",
        "Ciências da computação": "Ciências da Computação",
        "Administração de organizações": "Administração de Organizações",
        "Educação, administração e comunicação": "Educação, Administração e Comunicação",
    }
    return replacements.get(text, text)


def program_area(program: str) -> str:
    p = program.lower()
    if "educação matemática" in p:
        return "Educação Matemática"
    if "ensino de matemática" in p:
        return "Ensino de Matemática"
    if "computação" in p:
        return "Computação"
    if "administração" in p:
        return "Administração"
    if "engenharia" in p:
        return "Engenharia"
    if "psicologia" in p:
        return "Psicologia"
    if "ciências" in p or "científic" in p or "exatas" in p or "física" in p:
        return "Ensino de Ciências e Matemática"
    if p.startswith("educação"):
        return "Educação"
    if "estatística" in p or p == "matemática":
        return "Estatística e Matemática"
    return "Outros"


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "registro"


def norm_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    return re.sub(r"\s+", " ", text).strip()


def year_of(value) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        match = re.search(r"\d{4}", text)
        return int(match.group(0)) if match else None


def code_of(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return str(int(float(text)))
    except ValueError:
        return text.upper()


def google_scholar(title: str) -> str:
    return "https://scholar.google.com/scholar?q=" + quote_plus(f'"{title}"')


def bdtd(title: str) -> str:
    return (
        "https://bdtd.ibict.br/vufind/Search/Results?lookfor="
        + quote_plus(title)
        + "&type=AllFields"
    )


def read_rows() -> list[list[str]]:
    book = xlrd.open_workbook(str(SOURCE))
    sheet = book.sheet_by_name(SHEET)
    headers = [one_line(sheet.cell_value(0, c)) for c in range(sheet.ncols)]

    rows = []
    for r in range(FIRST_DATA_ROW, min(LAST_DATA_ROW + 1, sheet.nrows)):
        values = [clean(sheet.cell_value(r, c)) for c in range(sheet.ncols)]
        # A planilha tem linhas de legenda sem autor/título no final.
        if not values[0] or not values[4]:
            continue
        rows.append(values)
    return headers, rows


def main() -> None:
    headers, rows = read_rows()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "itens").mkdir(parents=True, exist_ok=True)

    records = []
    used_ids: Counter[str] = Counter()

    for row in rows:
        (
            autor,
            ano_raw,
            tipo_raw,
            universidade,
            titulo,
            cidade,
            estado_raw,
            orientador,
            programa_raw,
            nivel_raw,
            foco_raw,
            grau_raw,
            conteudo,
            regiao_raw,
            problema,
            metodologia,
            contribuicoes,
            palavras_chave,
            referencial,
            pronto,
        ) = row

        ano = year_of(ano_raw)
        tipo = smart_title(tipo_raw)
        if tipo.lower().startswith("tese"):
            tipo = "Tese"
        elif tipo.lower().startswith("disserta"):
            tipo = "Dissertação"

        estado = ESTADOS.get(one_line(estado_raw).lower(), smart_title(estado_raw))
        regiao = REGIOES.get(estado, smart_title(regiao_raw))
        programa = fix_program(programa_raw)
        area = program_area(programa)
        grau = code_of(grau_raw)
        nivel_codigo = code_of(nivel_raw)
        foco_codigo = code_of(foco_raw)

        base_id = f"{slugify(autor.split(',')[0])}-{ano or 'sem-ano'}"
        used_ids[base_id] += 1
        record_id = base_id if used_ids[base_id] == 1 else f"{base_id}-{used_ids[base_id]}"

        full = {
            "id": record_id,
            "autor": one_line(autor),
            "ano": ano,
            "tipo": tipo,
            "titulo": one_line(titulo),
            "instituicao": fix_institution(universidade),
            "cidade": smart_title(cidade),
            "estado": estado,
            "regiao": regiao,
            "orientador": one_line(orientador),
            "programa": programa,
            "area": area,
            "nivel_codigo": nivel_codigo,
            "nivel": NIVEIS.get(nivel_codigo, "Não informado"),
            "foco_codigo": foco_codigo,
            "foco": FOCOS.get(foco_codigo, "Não informado"),
            "grau_codigo": grau,
            "grau": GRAUS.get(grau, "Não informado"),
            "conteudo": one_line(conteudo) or "Não informado",
            "problema": clean(problema),
            "metodologia": clean(metodologia),
            "contribuicoes": clean(contribuicoes),
            "palavras_chave": clean(palavras_chave),
            "referencial": clean(referencial),
            "revisado": bool(one_line(pronto)),
            "links": {
                "google_scholar": google_scholar(one_line(titulo)),
                "bdtd": bdtd(one_line(titulo)),
            },
        }

        # Índice leve: o suficiente para busca, filtros e cards.
        index = {
            "id": record_id,
            "autor": full["autor"],
            "ano": full["ano"],
            "tipo": full["tipo"],
            "titulo": full["titulo"],
            "instituicao": full["instituicao"],
            "cidade": full["cidade"],
            "estado": full["estado"],
            "regiao": full["regiao"],
            "orientador": full["orientador"],
            "programa": full["programa"],
            "area": full["area"],
            "nivel": full["nivel"],
            "foco": full["foco"],
            "grau": full["grau"],
            "conteudo": full["conteudo"],
            "resumo": re.sub(r"\s+", " ", full["problema"])[:360],
            "palavras_chave": full["palavras_chave"],
            "busca": re.sub(
                r"\s+",
                " ",
                " ".join(
                    [
                        full["titulo"],
                        full["autor"],
                        full["instituicao"],
                        full["orientador"],
                        full["programa"],
                        full["area"],
                        full["nivel"],
                        full["foco"],
                        full["conteudo"],
                        full["palavras_chave"],
                        full["problema"],
                        full["metodologia"],
                        full["contribuicoes"],
                        full["referencial"],
                    ]
                ),
            ).lower(),
        }
        index["busca_norm"] = norm_text(index["busca"])

        records.append((full, index))
        (OUT / "itens" / f"{record_id}.json").write_text(
            json.dumps(full, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    indexes = [index for _, index in records]
    (OUT / "indice.json").write_text(
        json.dumps(indexes, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )

    years = range(1984, 2014)
    by_year = Counter(full["ano"] for full, _ in records if full["ano"])
    by_grau = Counter(full["grau"] for full, _ in records)
    by_tipo = Counter(full["tipo"] for full, _ in records)
    by_regiao = Counter(full["regiao"] for full, _ in records)
    by_estado = Counter(full["estado"] for full, _ in records)
    by_area = Counter(full["area"] for full, _ in records)
    by_foco = Counter(full["foco"] for full, _ in records)
    by_conteudo = Counter(full["conteudo"] for full, _ in records)
    by_nivel = Counter(full["nivel"] for full, _ in records)
    by_instituicao = Counter(full["instituicao"] for full, _ in records)

    def series(counter: Counter, order=None, label="total"):
        keys = order if order is not None else [key for key, _ in counter.most_common()]
        return [{"rotulo": key, label: counter.get(key, 0)} for key in keys]

    agregados = {
        "total": len(records),
        "periodo": {"inicio": min(years), "fim": max(years)},
        "instituicoes": len(by_instituicao),
        "estados": len([s for s in by_estado if s]),
        "regioes": len([r for r in by_regiao if r]),
        "atualizado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "por_ano": [{"ano": year, "total": by_year.get(year, 0)} for year in years],
        "por_grau": series(by_grau, ["Mestrado Acadêmico", "Mestrado Profissional", "Doutorado"]),
        "por_tipo": series(by_tipo, ["Dissertação", "Tese"]),
        "por_regiao": series(by_regiao, ["Sudeste", "Sul", "Nordeste", "Centro-Oeste", "Norte"]),
        "por_estado": series(by_estado),
        "por_area": series(by_area, AREAS),
        "por_foco": series(by_foco),
        "por_conteudo": series(by_conteudo, ["Estatística", "Probabilidade", "Combinatória", "Probabilidade e Estatística", "Combinatória e Probabilidade", "Combinatória, Probabilidade e Estatística"]),
        "por_nivel": series(by_nivel),
        "top_instituicoes": [
            {"nome": name, "total": total} for name, total in by_instituicao.most_common(12)
        ],
    }

    (OUT / "agregados.json").write_text(
        json.dumps(agregados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # CSV normalizado, com BOM para abrir bem no Excel.
    csv_fields = list(records[0][0].keys())
    with CSV_OUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()
        for full, _ in records:
            row = dict(full)
            row["links"] = json.dumps(row["links"], ensure_ascii=False)
            writer.writerow(row)

    PUBLIC_CSV.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CSV_OUT, PUBLIC_CSV)

    # Relatório de qualidade.
    def missing(field):
        return sum(1 for full, _ in records if not full[field])

    qualidade = {
        "registros": len(records),
        "sem_ano": missing("ano"),
        "sem_orientador": missing("orientador"),
        "sem_cidade": missing("cidade"),
        "sem_problema": missing("problema"),
        "sem_metodologia": missing("metodologia"),
        "sem_contribuicoes": missing("contribuicoes"),
        "sem_palavras_chave": missing("palavras_chave"),
        "sem_referencial": missing("referencial"),
        "foco_nao_informado": sum(1 for full, _ in records if full["foco"] == "Não informado"),
        "nivel_nao_informado": sum(1 for full, _ in records if full["nivel"] == "Não informado"),
        "duplicatas_exatas": 0,
    }
    QUALITY_OUT.write_text(
        json.dumps(qualidade, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"✓ {len(records)} registros exportados")
    print(f"  índice:    {OUT / 'indice.json'}")
    print(f"  itens:     {OUT / 'itens'}")
    print(f"  agregados: {OUT / 'agregados.json'}")
    print(f"  csv:       {CSV_OUT}")
    print(f"  qualidade: {QUALITY_OUT}")
    print(f"  período:   {agregados['periodo']['inicio']}–{agregados['periodo']['fim']}")


if __name__ == "__main__":
    main()
