#!/usr/bin/env python3
"""Render docs/sdlc-map.json as docs/sdlc-map.svg: one column per stage, the same rows lined up across columns.

Each entry in a cell is one point, drawn as a bullet and wrapped to the column width.
A point starting with "+" arrives in the next release and is drawn in amber.
A point starting with "~" is planned and is drawn grey with a dashed outline.
"loops" are drawn as arrows above the stage headers (going back), "skips" as dashed arrows below the grid.
Usage: python3 tools/render-sdlc-map.py   (no dependencies)
"""
import json
from html import escape
from pathlib import Path

root = Path(__file__).resolve().parent.parent
data = json.loads((root / "docs/sdlc-map.json").read_text())

COL_W, GAP, LABEL_W, PAD = 250, 22, 104, 24
LINE_H, CARD_PAD, ROW_GAP, HEADER_H = 17, 10, 10, 40
FONT_SIZE, BULLET_GAP, TEXT_INDENT = 12.5, 5, 22   # text starts TEXT_INDENT px into the card
TITLE_H = 70
LOOP_H, SKIP_H = 64, 64   # space above the headers for loops, below the grid for skips
FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
INK, MUTED, BORDER, CARD = "#1f2328", "#59636e", "#d0d7de", "#f6f8fa"
NEXT_INK, NEXT_BG = "#9a6700", "#fff8c5"
PLAN_INK, PLAN_LINE = "#6e7781", "#8c959f"
ACCENT = "#0969da"
LOOP_INK, SKIP_INK = "#8250df", "#6e7781"

stages, rows = data["stages"], data["rows"]

def char_w(c):
    # Rough Helvetica widths in em, enough to wrap without measuring fonts.
    if c in "il.,:;'|!()[]/ fjtr-": return 0.3
    if c in "mwMW@": return 0.85
    if c.isupper() or c in "<>_?%&": return 0.66
    return 0.55

def wrap(text):
    max_w = (COL_W - TEXT_INDENT - 8) / FONT_SIZE
    lines, line = [], ""
    for word in text.split(" "):
        test = f"{line} {word}" if line else word
        if line and sum(map(char_w, test)) > max_w:
            lines.append(line)
            line = word
        else:
            line = test
    return lines + [line]

def points(stage, row):
    for item in stage.get(row, []):
        kind = item[0] if item[:1] in ("+", "~") else ""
        yield kind, wrap(item[len(kind):])

def cell_h(stage, row):
    pts = list(points(stage, row))
    return sum(len(lines) for _, lines in pts) * LINE_H + max(len(pts) - 1, 0) * BULLET_GAP

row_h = [max(cell_h(s, r) for s in stages) + 2 * CARD_PAD + 4 for r in rows]

width = PAD * 2 + LABEL_W + len(stages) * COL_W + (len(stages) - 1) * GAP
head_y = PAD + TITLE_H + (LOOP_H if data.get("loops") else 0)
grid_top = head_y + HEADER_H + 12
grid_h = sum(row_h) + ROW_GAP * (len(rows) - 1)
grid_bottom = grid_top + grid_h
height = grid_bottom + (SKIP_H if data.get("skips") else 0) + PAD

out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="{FONT}">',
       f'<rect width="100%" height="100%" fill="#ffffff"/>',
       '<defs>' + "".join(
           f'<marker id="{name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
           f'<path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
           for name, color in (("arrow", ACCENT), ("arrow-loop", LOOP_INK), ("arrow-skip", SKIP_INK))) + '</defs>',
       f'<text x="{PAD}" y="{PAD + 22}" font-size="22" font-weight="600" fill="{INK}">{escape(data["title"])}</text>',
       f'<text x="{PAD}" y="{PAD + 48}" font-size="13" fill="{MUTED}">{escape(data["subtitle"])}</text>']

def col_x(i):
    return PAD + LABEL_W + i * (COL_W + GAP)

def col_mid(n):   # n is the stage number, 1-based
    return col_x(n - 1) + COL_W / 2

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
        out.append(f'<rect x="{x}" y="{y}" width="{COL_W}" height="{h}" rx="6" fill="{CARD}" stroke="{BORDER}"/>')
        ty = y + CARD_PAD + 13
        for kind, lines in points(stage, r):
            ink, style, box_h = INK, "", len(lines) * LINE_H
            if kind == "+":
                ink = NEXT_INK
                out.append(f'<rect x="{x + 5}" y="{ty - 13}" width="{COL_W - 10}" height="{box_h}" rx="3" fill="{NEXT_BG}"/>')
            elif kind == "~":
                ink, style = PLAN_INK, ' font-style="italic"'
                out.append(f'<rect x="{x + 5}" y="{ty - 13}" width="{COL_W - 10}" height="{box_h}" rx="3" fill="none" stroke="{PLAN_LINE}" stroke-dasharray="3 3"/>')
            out.append(f'<circle cx="{x + 13}" cy="{ty - 4}" r="2.2" fill="{ink if kind else MUTED}"/>')
            for line in lines:
                out.append(f'<text x="{x + TEXT_INDENT}" y="{ty}" font-size="{FONT_SIZE}" fill="{ink}"{style}>{escape(line)}</text>')
                ty += LINE_H
            ty += BULLET_GAP
    y += h + ROW_GAP

# Loops: up from the later stages' headers, back along a line above them, down into the earlier stage.
for loop in data.get("loops", []):
    line_y = head_y - 26
    start, end = col_mid(loop["from"]), col_mid(loop["to"])
    out.append(f'<path d="M{start},{head_y - 2} V{line_y} H{end} V{head_y - 3}" fill="none" stroke="{LOOP_INK}" stroke-width="2" marker-end="url(#arrow-loop)"/>')
    for n in loop.get("also_from", []):
        out.append(f'<path d="M{col_mid(n)},{head_y - 2} V{line_y}" stroke="{LOOP_INK}" stroke-width="2"/>')
        out.append(f'<circle cx="{col_mid(n)}" cy="{line_y}" r="3.5" fill="{LOOP_INK}"/>')
    out.append(f'<text x="{(start + end) / 2}" y="{line_y - 8}" font-size="12.5" font-weight="600" fill="{LOOP_INK}" text-anchor="middle">↺ {escape(loop["label"])}</text>')

# Skips: down from under one stage, along a dashed line below the grid, up into a later stage.
for skip in data.get("skips", []):
    line_y = grid_bottom + 24
    start, end = col_mid(skip["from"]) + 24, col_mid(skip["to"]) - 24
    out.append(f'<path d="M{start},{grid_bottom + 2} V{line_y} H{end} V{grid_bottom + 3}" fill="none" stroke="{SKIP_INK}" stroke-width="1.6" stroke-dasharray="5 4" marker-end="url(#arrow-skip)"/>')
    out.append(f'<text x="{(start + end) / 2}" y="{line_y + 18}" font-size="12" fill="{SKIP_INK}" text-anchor="middle">{escape(skip["label"])}</text>')

out.append("</svg>")
(root / "docs/sdlc-map.svg").write_text("\n".join(out) + "\n")
print(f"Wrote docs/sdlc-map.svg ({width}x{height})")
