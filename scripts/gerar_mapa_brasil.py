#!/usr/bin/env python3
"""Gera a malha simplificada dos estados brasileiros para o mapa do panorama."""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MALHA = ROOT / "dados" / "malha_uf.json"
ESTADOS = ROOT / "dados" / "estados_ibge.json"
OUT = ROOT / "site/public/data/mapa-brasil.json"

REGIOES = {
    "AC": "Norte", "AM": "Norte", "AP": "Norte", "PA": "Norte", "RO": "Norte", "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste", "PB": "Nordeste",
    "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MS": "Centro-Oeste", "MT": "Centro-Oeste",
}

WIDTH, HEIGHT, PAD = 760, 800, 18


def mercator(lat: float) -> float:
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def rdp(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points
    first, last = points[0], points[-1]
    dx, dy = last[0] - first[0], last[1] - first[1]
    norm = math.hypot(dx, dy)
    best, index = 0.0, 0
    for i in range(1, len(points) - 1):
        if norm == 0:
            distance = math.hypot(points[i][0] - first[0], points[i][1] - first[1])
        else:
            distance = abs(dy * points[i][0] - dx * points[i][1] + last[0] * first[1] - last[1] * first[0]) / norm
        if distance > best:
            best, index = distance, i
    if best > epsilon:
        return rdp(points[: index + 1], epsilon)[:-1] + rdp(points[index:], epsilon)
    return [first, last]


def centroid(ring: list[tuple[float, float]]) -> tuple[float, float]:
    area = cx = cy = 0.0
    for i in range(len(ring) - 1):
        x0, y0 = ring[i]
        x1, y1 = ring[i + 1]
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(area) < 1e-9:
        return ring[0]
    area *= 0.5
    return (cx / (6 * area), cy / (6 * area))


def rings(feature: dict) -> list[list[list[float]]]:
    geometry = feature["geometry"]
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"][0]]
    return [polygon[0] for polygon in geometry["coordinates"]]


def main() -> None:
    malha = json.loads(MALHA.read_text())
    estados = {str(state["id"]): state for state in json.loads(ESTADOS.read_text())}

    raw = []
    all_points = []
    for feature in malha["features"]:
        code = str(feature["properties"]["codarea"])
        state = estados[code]
        uf = state["sigla"]
        largest = max(rings(feature), key=len)
        projected = []
        for lon, lat in largest:
            x = math.radians(lon)
            y = -mercator(lat)
            projected.append((x, y))
        all_points.extend(projected)
        raw.append((uf, state["nome"], projected))

    min_x = min(point[0] for point in all_points)
    max_x = max(point[0] for point in all_points)
    min_y = min(point[1] for point in all_points)
    max_y = max(point[1] for point in all_points)
    scale = min((WIDTH - 2 * PAD) / (max_x - min_x), (HEIGHT - 2 * PAD) / (max_y - min_y))
    offset_x = (WIDTH - (max_x - min_x) * scale) / 2 - min_x * scale
    offset_y = (HEIGHT - (max_y - min_y) * scale) / 2 - min_y * scale

    result = []
    for uf, name, points in raw:
        transformed = [(x * scale + offset_x, y * scale + offset_y) for x, y in points]
        simplified = rdp(transformed, 0.7)
        if len(simplified) < 3:
            simplified = transformed
        cx, cy = centroid(simplified)
        path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in simplified) + " Z"
        result.append(
            {
                "uf": uf,
                "nome": name,
                "regiao": REGIOES[uf],
                "path": path,
                "cx": round(cx, 1),
                "cy": round(cy, 1),
            }
        )

    result.sort(key=lambda entry: entry["uf"])
    OUT.write_text(
        json.dumps({"viewBox": f"0 0 {WIDTH} {HEIGHT}", "states": result}, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"✓ {len(result)} estados, {OUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
