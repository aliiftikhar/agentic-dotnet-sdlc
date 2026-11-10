#!/usr/bin/env python3
"""Render docs/sdlc-map.json as docs/sdlc-map.svg: one column per stage, the same rows lined up across columns.

A line starting with "+" arrives in the next release and is drawn in amber.
A line starting with "~" is planned and is drawn grey with a dashed outline.
Usage: python3 tools/render-sdlc-map.py   (no dependencies)
"""
import json
from html import escape
from pathlib import Path

root = Path(__file__).resolve().parent.parent
data = json.loads((root / "docs/sdlc-map.json").read_text())

COL_W, GAP, LABEL_W, PAD = 250, 22, 104, 24
LINE_H, CARD_PAD, ROW_GAP, HEADER_H = 17, 10, 10, 40
TITLE_H = 70
FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
INK, MUTED, BORDER, CARD = "#1f2328", "#59636e", "#d0d7de", "#f6f8fa"
NEXT_INK, NEXT_BG = "#9a6700", "#fff8c5"
PLAN_INK, PLAN_LINE = "#6e7781", "#8c959f"
ACCENT = "#0969da"

stages, rows = data["stages"], data["rows"]
row_h = [max(len(s.get(r, [])) for s in stages) * LINE_H + 2 * CARD_PAD + 4 for r in rows]

width = PAD * 2 + LABEL_W + len(stages) * COL_W + (len(stages) - 1) * GAP
grid_top = PAD + TITLE_H + HEADER_H + 12
grid_h = sum(row_h) + ROW_GAP * (len(rows) - 1)
loops_top = grid_top + grid_h + 24
height = loops_top + len(data["loops"]) * 20 + PAD

out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="{FONT}">',
       f'<rect width="100%" height="100%" fill="#ffffff"/>',
       '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
       f'<path d="M0,0 L10,5 L0,10 z" fill="{ACCENT}"/></marker></defs>',
       f'<text x="{PAD}" y="{PAD + 22}" font-size="22" font-weight="600" fill="{INK}">{escape(data["title"])}</text>',
       f'<text x="{PAD}" y="{PAD + 48}" font-size="13" fill="{MUTED}">{escape(data["subtitle"])}</text>']

def col_x(i):
    return PAD + LABEL_W + i * (COL_W + GAP)

head_y = PAD + TITLE_H
for i, stage in enumerate(stages):
    x = col_x(i)
    out.append(f'<rect x="{x}" y="{head_y}" width="{COL_W}" height="{HEADER_H}" rx="8" fill="{ACCENT}"/>')
    out.append(f'<text x="{x + COL_W / 2}" y="{head_y + 26}" font-size="15" font-weight="600" fill="#ffffff" text-anchor="middle">{escape(stage["name"])}</text>')
    if i < len(stages) - 1:
        ay = head_y + HEADER_H / 2
        out.append(f'<line x1="{x + COL_W + 2}" y1="{ay}" x2="{x + COL_W + GAP - 2}" y2="{ay}" stroke="{ACCENT}" stroke-width="2" marker-end="url(#arrow)"/>')

y = grid_top
for r, h in zip(rows, row_h):
    out.append(f'<text x="{PAD}" y="{y + CARD_PAD + 13}" font-size="13" font-weight="600" fill="{MUTED}">{escape(r)}</text>')
    for i, stage in enumerate(stages):
        x = col_x(i)
        lines = stage.get(r, [])
        out.append(f'<rect x="{x}" y="{y}" width="{COL_W}" height="{h}" rx="6" fill="{CARD}" stroke="{BORDER}"/>')
        ty = y + CARD_PAD + 13
        for line in lines:
            nxt, planned = line.startswith("+"), line.startswith("~")
            text = line[1:] if nxt or planned else line
            ink, style = INK, ""
            if nxt:
                ink = NEXT_INK
                out.append(f'<rect x="{x + 5}" y="{ty - 13}" width="{COL_W - 10}" height="{LINE_H}" rx="3" fill="{NEXT_BG}"/>')
            elif planned:
                ink, style = PLAN_INK, ' font-style="italic"'
                out.append(f'<rect x="{x + 5}" y="{ty - 13}" width="{COL_W - 10}" height="{LINE_H}" rx="3" fill="none" stroke="{PLAN_LINE}" stroke-dasharray="3 3"/>')
            out.append(f'<text x="{x + 10}" y="{ty}" font-size="12.5" fill="{ink}"{style}>{escape(text)}</text>')
            ty += LINE_H
    y += h + ROW_GAP

for k, note in enumerate(data["loops"]):
    out.append(f'<text x="{PAD}" y="{loops_top + k * 20}" font-size="12.5" fill="{MUTED}">↺ {escape(note)}</text>')

out.append("</svg>")
(root / "docs/sdlc-map.svg").write_text("\n".join(out) + "\n")
print(f"Wrote docs/sdlc-map.svg ({width}x{height})")
