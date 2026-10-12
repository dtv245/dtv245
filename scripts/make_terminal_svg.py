#!/usr/bin/env python3
"""Generate assets/terminal-intro.svg: an animated "terminal" intro banner.

Edit the LINES list below, then run:
    python scripts/make_terminal_svg.py            # animated (typing effect)
    python scripts/make_terminal_svg.py --static   # no animation (for previews)
"""
import argparse
from html import escape
from pathlib import Path

# ("cmd", text) is typed after a "$" prompt; ("out", text) appears as output.
# Optional third item for "out" lines: a colour (the line is then bold).
LINES = [
    ("cmd", "whoami"),
    ("out", "Dang The Vu", "#58a6ff"),
    ("cmd", "cat role.txt"),
    ("out", "Full Stack Developer · React · TypeScript"),
    ("cmd", "cat location.txt"),
    ("out", "Hanoi, Vietnam"),
    ("cmd", "ls stack/"),
    ("out", "react  typescript  vite  tailwind  antd  cpp  python"),
]
TITLE = "dtv245 — zsh"

W, LINE_H, CHAR_W = 820, 26, 9.0
TOP, LEFT = 72, 28
GREEN, WHITE, GREY = "#3fb950", "#e6edf3", "#8b949e"
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"


def build(static: bool) -> str:
    rows = len(LINES) + 1                       # + final prompt with cursor
    height = TOP + rows * LINE_H + 8
    parts, clips = [], []
    t = 0.6
    for i, item in enumerate(LINES):
        kind, text = item[0], item[1]
        y = TOP + i * LINE_H
        if kind == "cmd":
            n = len(text)
            dur = max(n * 0.045, 0.2)
            prompt_anim = "" if static else (
                f'<animate attributeName="opacity" from="0" to="1" dur="0.01s" begin="{t:.2f}s" fill="freeze"/>')
            parts.append(
                f'<text x="{LEFT}" y="{y}" fill="{GREEN}" opacity="{1 if static else 0}">$'
                f'{prompt_anim}</text>')
            x0 = LEFT + 2 * CHAR_W
            if static:
                parts.append(f'<text x="{x0}" y="{y}" fill="{WHITE}">{escape(text)}</text>')
            else:
                values = [f"{k * CHAR_W:.1f}" for k in range(n + 1)]
                values[-1] = f"{n * CHAR_W + 24:.1f}"      # last step reveals everything
                clips.append(
                    f'<clipPath id="c{i}"><rect x="{x0}" y="{y - 17}" width="0" height="24">'
                    f'<animate attributeName="width" values="{";".join(values)}" calcMode="discrete" '
                    f'dur="{dur:.2f}s" begin="{t:.2f}s" fill="freeze"/></rect></clipPath>')
                parts.append(f'<text x="{x0}" y="{y}" fill="{WHITE}" clip-path="url(#c{i})">{escape(text)}</text>')
            t += dur + 0.35
        else:
            colour = item[2] if len(item) > 2 else GREY
            weight = ' font-weight="bold"' if len(item) > 2 else ""
            anim = "" if static else (
                f'<animate attributeName="opacity" from="0" to="1" dur="0.2s" begin="{t:.2f}s" fill="freeze"/>')
            parts.append(
                f'<text x="{LEFT}" y="{y}" fill="{colour}"{weight} opacity="{1 if static else 0}">'
                f'{escape(text)}{anim}</text>')
            t += 0.55

    y_last = TOP + len(LINES) * LINE_H
    cursor_anim = "" if static else (
        f'<animate attributeName="opacity" values="1;0" calcMode="discrete" dur="1s" '
        f'begin="{t:.2f}s" repeatCount="indefinite"/>')
    parts.append(f'<text x="{LEFT}" y="{y_last}" fill="{GREEN}">$</text>')
    parts.append(
        f'<rect x="{LEFT + 2 * CHAR_W}" y="{y_last - 15}" width="9" height="19" fill="{WHITE}" '
        f'opacity="{1 if static else 0}">{cursor_anim}</rect>')

    body = "\n    ".join(parts)
    defs_clips = "\n    ".join(clips)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}" role="img" aria-label="Terminal intro: Dang The Vu, Full Stack Developer, Hanoi, Vietnam">
  <title>Terminal intro</title>
  <defs>
    <linearGradient id="bar" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#1f6feb"/><stop offset="1" stop-color="#8957e5"/>
    </linearGradient>
    {defs_clips}
  </defs>
  <rect x="1" y="1" width="{W - 2}" height="{height - 2}" rx="12" fill="#0d1117" stroke="#30363d" stroke-width="2"/>
  <path d="M13 1 H{W - 13} A12 12 0 0 1 {W - 1} 13 V36 H1 V13 A12 12 0 0 1 13 1 Z" fill="#161b22"/>
  <rect x="1" y="36" width="{W - 2}" height="2" fill="url(#bar)"/>
  <circle cx="24" cy="19" r="6" fill="#ff5f56"/>
  <circle cx="44" cy="19" r="6" fill="#ffbd2e"/>
  <circle cx="64" cy="19" r="6" fill="#27c93f"/>
  <text x="{W / 2}" y="24" text-anchor="middle" font-family="{FONT}" font-size="13" fill="{GREY}">{escape(TITLE)}</text>
  <g font-family="{FONT}" font-size="15" xml:space="preserve">
    {body}
  </g>
</svg>
'''


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--static", action="store_true", help="no animation (preview)")
    ap.add_argument("--out", default="assets/terminal-intro.svg")
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(args.static), encoding="utf-8")
    print(f"wrote {out}")
