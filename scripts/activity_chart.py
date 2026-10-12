#!/usr/bin/env python3
"""Draw two GitHub activity charts as standalone SVG files (standard library only).

  timeline-{light,dark}.svg   contributions per month, grouped by year
  languages-{light,dark}.svg  share of code by language, by the year a repo was created

Usage:
    GH_TOKEN=<token> python scripts/activity_chart.py --user dtv245 --out assets
    python scripts/activity_chart.py --demo --out preview      # fake data, no network
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import random
import urllib.request
from collections import defaultdict
from html import escape
from pathlib import Path

API_URL = "https://api.github.com/graphql"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

THEMES = {
    "light": {"text": "#1f2328", "muted": "#656d76", "grid": "#d8dee4", "bar": "#0969da"},
    "dark": {"text": "#e6edf3", "muted": "#8b949e", "grid": "#30363d", "bar": "#58a6ff"},
}
FALLBACK_COLORS = ["#0969da", "#8957e5", "#bf3989", "#cf222e", "#bc4c00", "#9a6700", "#1a7f37", "#0a7d8c"]
OTHER_COLOR = "#8b949e"

# --------------------------------------------------------------------------- GitHub API

Q_CREATED = "query($login:String!){user(login:$login){createdAt}}"
Q_CALENDAR = """
query($login:String!,$from:DateTime!,$to:DateTime!){
  user(login:$login){
    contributionsCollection(from:$from,to:$to){
      contributionCalendar{weeks{contributionDays{date contributionCount}}}
    }
  }
}"""
Q_REPOS = """
query($login:String!,$after:String){
  user(login:$login){
    repositories(first:50,after:$after,ownerAffiliations:OWNER,isFork:false,privacy:PUBLIC){
      pageInfo{hasNextPage endCursor}
      nodes{
        createdAt
        languages(first:8,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}
      }
    }
  }
}"""


def gql(query: str, variables: dict, token: str) -> dict:
    req = urllib.request.Request(
        API_URL,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-activity-chart",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise SystemExit(json.dumps(payload["errors"], indent=2))
    return payload["data"]


def fetch_monthly(user: str, token: str) -> dict[tuple[int, int], int]:
    created = gql(Q_CREATED, {"login": user}, token)["user"]["createdAt"]
    utc = dt.timezone.utc
    now = dt.datetime.now(utc)
    monthly: dict[tuple[int, int], int] = defaultdict(int)
    for year in range(int(created[:4]), now.year + 1):
        start = dt.datetime(year, 1, 1, tzinfo=utc)
        end = min(dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=utc), now)
        data = gql(Q_CALENDAR, {"login": user, "from": start.isoformat(), "to": end.isoformat()}, token)
        weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        for week in weeks:
            for day in week["contributionDays"]:
                date = dt.date.fromisoformat(day["date"])
                if date.year == year:          # the calendar pads partial weeks
                    monthly[(year, date.month)] += day["contributionCount"]
    return dict(monthly)


def fetch_languages(user: str, token: str) -> tuple[dict[int, dict[str, int]], dict[str, str]]:
    by_year: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    colors: dict[str, str] = {}
    after = None
    while True:
        data = gql(Q_REPOS, {"login": user, "after": after}, token)["user"]["repositories"]
        for repo in data["nodes"]:
            year = int(repo["createdAt"][:4])
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                by_year[year][name] += edge["size"]
                if edge["node"]["color"]:
                    colors[name] = edge["node"]["color"]
        if not data["pageInfo"]["hasNextPage"]:
            break
        after = data["pageInfo"]["endCursor"]
    return {y: dict(v) for y, v in by_year.items()}, colors


# --------------------------------------------------------------------------- helpers

def nice_step(raw: float) -> float:
    exp = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if raw <= m * exp:
            return m * exp
    return 10 * exp


def svg_open(w: int, h: int, label: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{escape(label)}" font-family="{FONT}">',
        f"<title>{escape(label)}</title>",
    ]


# --------------------------------------------------------------------------- charts

def timeline_svg(monthly: dict[tuple[int, int], int], theme: str) -> str:
    c = THEMES[theme]
    years = sorted({y for y, _ in monthly}) or [dt.date.today().year]
    W, H = 900, 280
    L, R, T, B = 44, 16, 44, 50
    pw, ph = W - L - R, H - T - B
    slot = pw / (len(years) * 12)
    bar_w = slot * 0.64

    vmax = max(monthly.values(), default=0)
    step = nice_step(max(vmax, 4) / 4)
    ticks = max(1, math.ceil(max(vmax, 1) / step))
    ymax = step * ticks

    def y_of(v: float) -> float:
        return T + ph - v / ymax * ph

    out = svg_open(W, H, "Contributions per month")
    out.append(f'<text x="{L}" y="24" font-size="14" font-weight="600" fill="{c["text"]}">Contributions per month</text>')
    for k in range(ticks + 1):
        v = k * step
        y = y_of(v)
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" stroke="{c["grid"]}" stroke-width="1"/>')
        out.append(f'<text x="{L - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="{c["muted"]}">{int(v):,}</text>')

    for yi, year in enumerate(years):
        x_year = L + yi * 12 * slot
        if yi:
            out.append(
                f'<line x1="{x_year:.1f}" y1="{T}" x2="{x_year:.1f}" y2="{T + ph + 6}" '
                f'stroke="{c["grid"]}" stroke-dasharray="3 3"/>')
        total = 0
        for month in range(1, 13):
            v = monthly.get((year, month), 0)
            total += v
            if v <= 0:
                continue
            x = x_year + (month - 1) * slot + (slot - bar_w) / 2
            top = y_of(v)
            h = max(T + ph - top, 2)
            out.append(
                f'<rect x="{x:.1f}" y="{T + ph - h:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="2" fill="{c["bar"]}">'
                f"<title>{year}-{month:02d}: {v:,} contributions</title></rect>")
        cx = x_year + 6 * slot
        out.append(f'<text x="{cx:.1f}" y="{H - 24}" text-anchor="middle" font-size="13" font-weight="600" fill="{c["text"]}">{year}</text>')
        out.append(f'<text x="{cx:.1f}" y="{H - 8}" text-anchor="middle" font-size="11" fill="{c["muted"]}">{total:,}</text>')
    out.append("</svg>")
    return "\n".join(out)


def languages_svg(by_year: dict[int, dict[str, int]], colors: dict[str, str], theme: str, top_n: int = 7) -> str:
    c = THEMES[theme]
    years = sorted(y for y, langs in by_year.items() if sum(langs.values()) > 0)
    W, H = 900, 300
    L, R, T, B = 44, 16, 70, 34
    pw, ph = W - L - R, H - T - B

    overall: dict[str, int] = defaultdict(int)
    for langs in by_year.values():
        for name, size in langs.items():
            overall[name] += size
    top = [name for name, _ in sorted(overall.items(), key=lambda kv: -kv[1])[:top_n]]
    palette = {name: colors.get(name) or FALLBACK_COLORS[i % len(FALLBACK_COLORS)] for i, name in enumerate(top)}
    palette["Other"] = OTHER_COLOR
    order = top + ["Other"]

    out = svg_open(W, H, "Share of code by language, by the year a repository was created")
    out.append(f'<text x="{L}" y="24" font-size="14" font-weight="600" fill="{c["text"]}">Languages by year a repo was started</text>')

    has_other = any(size for langs in by_year.values() for n, size in langs.items() if n not in top)
    x = L
    for name in order:
        if name == "Other" and not has_other:
            continue
        out.append(f'<rect x="{x}" y="38" width="10" height="10" rx="2" fill="{palette[name]}"/>')
        out.append(f'<text x="{x + 15}" y="47" font-size="11" fill="{c["muted"]}">{escape(name)}</text>')
        x += 15 + len(name) * 6.6 + 18

    for k, pct in enumerate((0, 50, 100)):
        y = T + ph - pct / 100 * ph
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" stroke="{c["grid"]}"/>')
        out.append(f'<text x="{L - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="{c["muted"]}">{pct}%</text>')

    if years:
        slot = pw / len(years)
        col_w = min(slot * 0.6, 90)
        for i, year in enumerate(years):
            langs = by_year[year]
            total = sum(langs.values())
            groups = {name: langs.get(name, 0) for name in top}
            groups["Other"] = total - sum(groups.values())
            cx = L + i * slot + slot / 2
            y_cursor = T + ph
            for name in order:
                size = groups.get(name, 0)
                if size <= 0:
                    continue
                h = size / total * ph
                y_cursor -= h
                out.append(
                    f'<rect x="{cx - col_w / 2:.1f}" y="{y_cursor:.1f}" width="{col_w:.1f}" height="{max(h - 1, 0.5):.1f}" '
                    f'fill="{palette[name]}"><title>{year} · {escape(name)}: {size / total:.0%}</title></rect>')
            out.append(f'<text x="{cx:.1f}" y="{H - 12}" text-anchor="middle" font-size="13" font-weight="600" fill="{c["text"]}">{year}</text>')
    out.append("</svg>")
    return "\n".join(out)


# --------------------------------------------------------------------------- demo data

def demo_data():
    rnd = random.Random(7)
    monthly = {(y, m): rnd.randint(0, 90) + (30 if y >= 2025 else 0)
               for y in range(2023, 2027) for m in range(1, 13) if not (y == 2023 and m < 3) and not (y == 2026 and m > 10)}
    langs = {
        2023: {"C++": 90_000, "Python": 30_000},
        2024: {"C++": 40_000, "Python": 70_000, "TypeScript": 20_000},
        2025: {"TypeScript": 300_000, "SCSS": 40_000, "Python": 20_000, "JavaScript": 10_000, "HTML": 8_000},
        2026: {"TypeScript": 120_000, "SCSS": 15_000, "Python": 10_000},
    }
    colors = {"C++": "#f34b7d", "Python": "#3572A5", "TypeScript": "#3178c6", "SCSS": "#c6538c",
              "JavaScript": "#f1e05a", "HTML": "#e34c26"}
    return monthly, langs, colors


# --------------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "dtv245"))
    ap.add_argument("--out", default="assets", help="output directory")
    ap.add_argument("--demo", action="store_true", help="use fake data (no network, no token)")
    args = ap.parse_args()

    if args.demo:
        monthly, by_year, colors = demo_data()
    else:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("Set GH_TOKEN (a GitHub token) or use --demo.")
        monthly = fetch_monthly(args.user, token)
        by_year, colors = fetch_languages(args.user, token)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (out_dir / f"timeline-{theme}.svg").write_text(timeline_svg(monthly, theme), encoding="utf-8")
        (out_dir / f"languages-{theme}.svg").write_text(languages_svg(by_year, colors, theme), encoding="utf-8")
    print(f"wrote 4 charts to {out_dir}/ for {args.user}")


if __name__ == "__main__":
    main()
