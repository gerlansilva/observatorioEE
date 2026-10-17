#!/usr/bin/env python3
"""Mantém apenas palavras-chave em português e complementa com a planilha."""

from __future__ import annotations

import glob
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "site/public/data/itens"

ENGLISH_WORDS = {
    "the", "and", "of", "in", "to", "for", "with", "on", "by", "from", "as",
    "teaching", "learning", "education", "statistics", "statistical", "probability",
    "mathematics", "mathematical", "students", "student", "teachers", "teacher",
    "school", "research", "study", "analysis", "data", "quality", "evaluation",
    "assessment", "attitudes", "attitude", "affectivity", "combinatorics",
    "computer", "software", "distance", "formation", "knowledge", "paradigms",
    "paradigm", "inference", "randomness", "reality", "determinism", "project",
    "works", "higher", "elementary", "pedagogy", "practice", "development",
    "professional", "applied", "administration", "statistic", "probability",
    "towards", "styles", "style", "multivariate", "variance", "quality",
    "logic", "classical", "bayesian", "associated", "teachers’", "teacher's",
}


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.lower()).strip()


def is_english(tag: str) -> bool:
    text = clean(tag)
    lowered = text.lower()
    if lowered.startswith(("e-learning", "distance education")):
        return True
    if " - study and teaching" in lowered or "- study and teaching" in lowered:
        return True
    if re.search(r"\b(of|and|the|in|for|with)\b", lowered):
        return True
    words = re.findall(r"[a-zà-ÿ’'-]+", lowered)
    if not words:
        return False
    english = sum(1 for word in words if word.strip("’'") in ENGLISH_WORDS)
    return english >= max(1, len(words) // 2)


def split_keywords(value: str) -> list[str]:
    text = re.sub(r"(^|\s)\d+[.)]\s*", " ", clean(value))
    parts = re.split(r"[;,.]", text)
    return [clean(part) for part in parts if clean(part)]


def main() -> None:
    changed = 0
    english_before = english_after = 0
    for path in sorted(glob.glob(str(ITEMS / "*.json"))):
        item = json.loads(Path(path).read_text(encoding="utf-8"))
        tags = [clean(tag) for tag in item.get("tags", []) if clean(tag)]
        english_before += sum(1 for tag in tags if is_english(tag))

        kept = [
            tag for tag in tags
            if not is_english(tag) and "possui palavras-chave" not in tag.lower()
        ]
        seen = {norm(tag) for tag in kept}
        for tag in split_keywords(item.get("palavras_chave", "")):
            if not tag or is_english(tag) or "possui palavras-chave" in tag.lower():
                continue
            key = norm(tag)
            if key not in seen:
                seen.add(key)
                kept.append(tag)

        # Preserva a ordem e limita o excesso.
        final = kept[:24]
        english_after += sum(1 for tag in final if is_english(tag))
        if final != item.get("tags", []):
            item["tags"] = final
            Path(path).write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1

    print(f"✓ {changed} fichas; tags em inglês: {english_before} → {english_after}")


if __name__ == "__main__":
    main()
