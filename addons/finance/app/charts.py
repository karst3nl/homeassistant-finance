"""Serverseitig erzeugte SVG-Charts – kein JavaScript, kein CDN, kein Build.

Alle Texte werden escapt; die erzeugten Strings sind daher auch bei
Buchungstexten oder Kategorienamen mit Sonderzeichen sicher einbettbar.
"""

from __future__ import annotations

import html
import math
import re

from money import format_cents

_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_FALLBACK_COLOR = "#41bdf5"


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _color(value: object) -> str:
    text = str(value or "")
    return text if _COLOR_RE.fullmatch(text) else _FALLBACK_COLOR


def bar_chart(months: list[dict], width: int = 640, height: int = 240) -> str:
    """Gruppierte Balken für Einnahmen und Ausgaben je Monat."""
    left, right, top, bottom = 96, 12, 16, 34
    plot_width = width - left - right
    plot_height = height - top - bottom
    maximum = max((max(m["income_cents"], m["expense_cents"]) for m in months), default=0) or 1

    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Monatsvergleich von Einnahmen und Ausgaben">'
    ]
    for fraction in (0, 0.5, 1):
        y = top + plot_height * (1 - fraction)
        parts.append(
            f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" />'
        )
        parts.append(
            f'<text class="axis" x="{left - 8}" y="{y + 4:.1f}" text-anchor="end">'
            f"{_esc(format_cents(round(maximum * fraction)))}</text>"
        )

    if months:
        slot = plot_width / len(months)
        bar_width = min(20, slot * 0.3)
        for index, month in enumerate(months):
            center = left + slot * (index + 0.5)
            for key, css_class, offset in (
                ("income_cents", "bar-income", -bar_width - 2),
                ("expense_cents", "bar-expense", 2),
            ):
                value = month[key]
                bar_height = plot_height * value / maximum
                bar_y = top + plot_height - bar_height
                parts.append(
                    f'<rect class="{css_class}" x="{center + offset:.1f}" '
                    f'y="{bar_y:.1f}" width="{bar_width:.1f}" '
                    f'height="{bar_height:.1f}" rx="2">'
                    f"<title>{_esc(month['period'])}: {_esc(format_cents(value))}</title></rect>"
                )
            label = month["period"][5:7] + "/" + month["period"][2:4]
            parts.append(
                f'<text class="axis" x="{center:.1f}" y="{height - 10}" '
                f'text-anchor="middle">{_esc(label)}</text>'
            )
    else:
        parts.append(
            f'<text class="axis" x="{width / 2:.0f}" y="{height / 2:.0f}" '
            'text-anchor="middle">Keine Daten</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def donut_chart(items: list[dict], size: int = 200) -> str:
    """Ringdiagramm mit einem Segment je Kategorie."""
    radius = 70
    circumference = 2 * math.pi * radius
    center = size / 2
    total = sum(item["total_cents"] for item in items)

    parts = [
        f'<svg class="donut" viewBox="0 0 {size} {size}" role="img" '
        'aria-label="Anteile nach Kategorie">',
        f'<circle class="donut-track" cx="{center}" cy="{center}" '
        f'r="{radius}" fill="none" stroke-width="22" />',
    ]
    offset = 0.0
    for item in items:
        if total <= 0:
            break
        length = circumference * item["total_cents"] / total
        parts.append(
            f'<circle cx="{center}" cy="{center}" r="{radius}" fill="none" '
            f'stroke="{_color(item.get("color"))}" stroke-width="22" '
            f'stroke-dasharray="{length:.2f} {circumference - length:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 {center} {center})">'
            f"<title>{_esc(item['name'])}: {_esc(format_cents(item['total_cents']))}"
            f" ({item.get('share', 0)} %)</title></circle>"
        )
        offset += length

    parts.append(
        f'<text class="donut-total" x="{center}" y="{center + 5}" '
        f'text-anchor="middle">{_esc(format_cents(total))}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def line_chart(points: list[dict], width: int = 640, height: int = 240) -> str:
    """Linie mit Fläche für den Saldo zum Monatsende."""
    left, right, top, bottom = 96, 12, 16, 34
    plot_width = width - left - right
    plot_height = height - top - bottom
    values = [point["total_cents"] for point in points]
    low, high = min([0, *values]), max([0, *values])
    span = high - low or 1
    low, high = low - span * 0.05, high + span * 0.05

    def y_position(value: int) -> float:
        return top + plot_height * (high - value) / (high - low)

    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Saldo-Verlauf zum Monatsende">'
    ]
    for label_value in (high, (high + low) / 2, low):
        y = y_position(label_value)
        parts.append(
            f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" />'
        )
        parts.append(
            f'<text class="axis" x="{left - 8}" y="{y + 4:.1f}" text-anchor="end">'
            f"{_esc(format_cents(round(label_value)))}</text>"
        )

    if not points:
        parts.append(
            f'<text class="axis" x="{width / 2:.0f}" y="{height / 2:.0f}" '
            'text-anchor="middle">Keine Daten</text>'
        )
        parts.append("</svg>")
        return "".join(parts)

    slot = plot_width / len(points)
    coordinates = [
        (left + slot * (index + 0.5), y_position(point["total_cents"]))
        for index, point in enumerate(points)
    ]
    zero_y = y_position(0)
    area_points = " ".join(f"{x:.1f},{y:.1f}" for x, y in coordinates)
    parts.append(
        f'<polygon class="chart-area" points="{coordinates[0][0]:.1f},{zero_y:.1f} '
        f'{area_points} {coordinates[-1][0]:.1f},{zero_y:.1f}" />'
    )
    parts.append(f'<polyline class="chart-line" points="{area_points}" />')
    for (x, y), point in zip(coordinates, points, strict=True):
        parts.append(
            f'<circle class="chart-dot" cx="{x:.1f}" cy="{y:.1f}" r="3">'
            f"<title>{_esc(point['period'])}: "
            f"{_esc(format_cents(point['total_cents']))}</title></circle>"
        )
        label = point["period"][5:7] + "/" + point["period"][2:4]
        parts.append(
            f'<text class="axis" x="{x:.1f}" y="{height - 10}" '
            f'text-anchor="middle">{_esc(label)}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)
