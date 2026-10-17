#!/usr/bin/env python3
"""
Gera uma miniatura editorial determinística para cada trabalho.
Sem imagens geradas: capa tipográfica com tipo, ano, título, autoria e instituição.
"""

from __future__ import annotations

import hashlib
import html
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "site/public/data/itens"
OUT = ROOT / "site/public/assets/images/thumbs"

PALETTE = [
    ("#174B57", "#D7E5E7"),
    ("#1B5563", "#D7E5E7"),
    ("#2E7D89", "#FFFFFF"),
    ("#123B45", "#D7E5E7"),
    ("#234E59", "#D7E5E7"),
    ("#1F6470", "#D7E5E7"),
]


def clean(value) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def esc(value: str) -> str:
    return html.escape(clean(value), quote=True)


def initials(name: str) -> str:
    parts = [part for part in clean(name).split() if len(part) > 1]
    if not parts:
        return "EE"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def surname(name: str) -> str:
    parts = clean(name).split()
    if not parts:
        return ""
    if len(parts) > 1 and parts[-1].lower() in {"junior", "júnior", "neto", "filho", "sobrinho"}:
        return f"{parts[-2]} {parts[-1]}"
    return parts[-1]


def wrap_lines(text: str, width: int, max_lines: int) -> list[str]:
    text = clean(text)
    if not text:
        return []
    lines = textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        if len(last) > width - 1:
            last = last[: width - 2].rstrip()
        lines[-1] = last.rstrip(" .,;:") + "…"
    return lines


def build_svg(item: dict, index: int) -> str:
    background, accent = PALETTE[int(hashlib.sha1(item["id"].encode()).hexdigest()[:8], 16) % len(PALETTE)]
    tipo = "TESE" if "tese" in clean(item.get("tipo")).lower() else "DISSERTAÇÃO"
    ano = clean(item.get("ano")) or "—"
    title = clean(item.get("titulo"))
    title_lines = wrap_lines(title, 30, 3)
    author = surname(item.get("autor")) or clean(item.get("autor")) or "Autoria não informada"
    institution = clean(item.get("instituicao") or item.get("instituicao_capes")) or "Instituição não informada"
    inst_lines = wrap_lines(institution, 52, 2)
    area = clean(item.get("area")) or clean(item.get("foco"))
    area = area[:42]

    # Título com corpo menor quando há muitas palavras.
    title_size = 30 if len(title) <= 90 else 26
    title_y = 132
    title_line_height = 36 if title_size == 30 else 32

    title_tspans = "".join(
        f'<tspan x="64" y="{title_y + i * title_line_height}">{esc(line)}</tspan>'
        for i, line in enumerate(title_lines)
    )
    inst_tspans = "".join(
        f'<tspan x="64" y="{414 + i * 19}">{esc(line)}</tspan>'
        for i, line in enumerate(inst_lines)
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480" width="640" height="480" role="img" aria-label="{esc(title[:80])}">
  <rect width="640" height="480" fill="{background}"/>
  <g opacity="0.10" stroke="{accent}" stroke-width="1">
    <path d="M0 80H640M0 400H640M40 0V480M600 0V480"/>
    <path d="M0 160H640M0 320H640M160 0V480M480 0V480" opacity="0.55"/>
  </g>
  <text x="40" y="52" fill="{accent}" font-family="Roboto, Arial, Helvetica, sans-serif" font-size="13" font-weight="700" letter-spacing="2.4">{tipo}</text>
  <text x="600" y="52" text-anchor="end" fill="{accent}" font-family="Roboto, Arial, Helvetica, sans-serif" font-size="20" font-weight="500">{esc(ano)}</text>
  <line x1="40" y1="76" x2="600" y2="76" stroke="{accent}" stroke-width="1" opacity="0.55"/>
  <rect x="40" y="112" width="4" height="{max(24, min(132, len(title_lines) * title_line_height + 4))}" fill="{accent}" opacity="0.9"/>
  <text fill="#FFFFFF" font-family="Roboto, Arial, Helvetica, sans-serif" font-size="{title_size}" font-weight="500" letter-spacing="0.1">{title_tspans}</text>
  <line x1="40" y1="360" x2="600" y2="360" stroke="{accent}" stroke-width="1" opacity="0.55"/>
  <text x="40" y="392" fill="#FFFFFF" font-family="Roboto, Arial, Helvetica, sans-serif" font-size="22" font-weight="600" letter-spacing="0.4">{esc(author)}</text>
  <text fill="{accent}" font-family="Roboto, Arial, Helvetica, sans-serif" font-size="13" opacity="0.92">{inst_tspans}</text>
  <text x="600" y="452" text-anchor="end" fill="{accent}" font-family="Roboto, Arial, Helvetica, sans-serif" font-size="11" opacity="0.8">{esc(area)}</text>
  <text x="600" y="392" text-anchor="end" fill="{accent}" font-family="Roboto, Arial, Helvetica, sans-serif" font-size="13" font-weight="700" letter-spacing="1.2">{initials(item.get("autor"))}</text>
</svg>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    paths = sorted(ITEMS.glob("*.json"))
    for position, path in enumerate(paths, start=1):
        item = json.loads(path.read_text(encoding="utf-8"))
        svg = build_svg(item, position)
        (OUT / f"{item['id']}.svg").write_text(svg, encoding="utf-8")
        item["thumbnail"] = f"./assets/images/thumbs/{item['id']}.svg"
        path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✓ {len(paths)} miniaturas geradas em {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
