#!/usr/bin/env python3
"""Refresh the generated parts of the profile README and the stats card.

Each generated part of README.md sits between <!-- NAME:START --> and
<!-- NAME:END --> markers; everything outside them is written by hand.
Reads public data only, through GH_TOKEN (the workflow's own token).
"""

import datetime
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

USER = os.environ.get("PROFILE_USER", "Commanderx-code")
API = "https://api.github.com"
ROOT = Path(__file__).resolve().parents[2]


def get(path, **params):
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USER}-profile",
    })
    token = os.environ.get("GH_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def own_repos():
    repos = get(f"/users/{USER}/repos", per_page=100, type="owner", sort="pushed")
    return [r for r in repos
            if not r["fork"] and not r["archived"] and not r["private"]
            and r["name"].lower() != USER.lower()]


def line(repo):
    description = (repo["description"] or "").strip()
    link = f"[**{repo['name']}**]({repo['html_url']})"
    return f"- {link}: {description}" if description else f"- {link}"


def recently_updated(repos):
    return "\n".join(line(r) for r in repos[:5])


def recent_pull_requests():
    found = get("/search/issues", q=f"author:{USER} type:pr is:public",
                sort="created", order="desc", per_page=6)
    lines = []
    for pr in found["items"]:
        repository = pr["repository_url"].removeprefix(f"{API}/repos/")
        state = "merged" if (pr.get("pull_request") or {}).get("merged_at") else pr["state"]
        title = pr["title"].replace("[", "(").replace("]", ")")
        lines.append(f"- [{title}]({pr['html_url']}) in "
                     f"[{repository}](https://github.com/{repository}) · {state}")
    return "\n".join(lines) or "- Nothing public yet."


def recent_stars():
    starred = get(f"/users/{USER}/starred", per_page=5)
    lines = []
    for repo in starred:
        description = (repo["description"] or "").strip()
        link = f"[{repo['full_name']}]({repo['html_url']})"
        lines.append(f"- {link}: {description}" if description else f"- {link}")
    return "\n".join(lines) or "- Nothing starred yet."


def replace(text, name, body):
    pattern = re.compile(rf"(<!-- {name}:START -->).*?(<!-- {name}:END -->)", re.S)
    if not pattern.search(text):
        sys.exit(f"README.md has no {name} markers")
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(2)}", text)


LANGUAGE_COLORS = {
    "Rust": "#dea584", "Python": "#3572A5", "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a", "Shell": "#89e051", "Svelte": "#ff3e00",
    "Nix": "#7e7eff", "QML": "#44a51c", "Lua": "#000080", "CSS": "#663399",
    "HTML": "#e34c26", "Java": "#b07219", "Go": "#00ADD8", "C": "#555555",
}


def stats_card(repos):
    releases = 0
    for repo in repos:
        page = 1
        while True:
            batch = get(f"/repos/{USER}/{repo['name']}/releases", per_page=100, page=page)
            releases += len(batch)
            if len(batch) < 100:
                break
            page += 1
    year_ago = (datetime.date.today() - datetime.timedelta(days=365)).isoformat()
    commits = get("/search/commits", q=f"author:{USER} committer-date:>{year_ago}",
                  per_page=1)["total_count"]
    merged = get("/search/issues", q=f"author:{USER} type:pr is:merged",
                 per_page=1)["total_count"]
    sizes = {}
    for repo in repos:
        for language, size in get(f"/repos/{USER}/{repo['name']}/languages").items():
            sizes[language] = sizes.get(language, 0) + size
    total = sum(sizes.values()) or 1
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:6]
    shown = sum(size for _, size in top) or 1

    figures = [("Public projects", len(repos)), ("Releases shipped", releases),
               ("Commits, last 12 months", commits), ("Pull requests merged", merged)]
    rows = []
    for i, (label, value) in enumerate(figures):
        y = 92 + i * 38
        rows.append(f'<text x="34" y="{y}" class="label">{html.escape(label)}</text>'
                    f'<text x="388" y="{y}" class="value" text-anchor="end">{value:,}</text>')

    bar, legend, x = [], [], 440.0
    width = 386.0
    for i, (language, size) in enumerate(top):
        share = size / total
        part = max(width * size / shown, 3)
        color = LANGUAGE_COLORS.get(language, "#9ea2bd")
        bar.append(f'<rect x="{x:.1f}" y="76" width="{part:.1f}" height="12" fill="{color}"/>')
        x += part
        lx, ly = 440 + (i % 2) * 196, 120 + (i // 2) * 34
        legend.append(f'<circle cx="{lx + 6}" cy="{ly - 5}" r="6" fill="{color}"/>'
                      f'<text x="{lx + 20}" y="{ly}" class="label">{html.escape(language)}'
                      f' <tspan class="dim">{share:.0%}</tspan></text>')

    updated = datetime.date.today().strftime("%B %-d, %Y")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="860" height="260" viewBox="0 0 860 260">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#1b2258"/><stop offset="0.6" stop-color="#0d0f2c"/><stop offset="1" stop-color="#140a2e"/>
    </linearGradient>
    <linearGradient id="rim" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#3bd2ff"/><stop offset="1" stop-color="#d040ff"/>
    </linearGradient>
    <clipPath id="bar"><rect x="440" y="76" width="{width:.0f}" height="12" rx="6"/></clipPath>
  </defs>
  <style>
    text {{ font-family: "Segoe UI", Ubuntu, "Helvetica Neue", Arial, sans-serif; }}
    .title {{ font-size: 20px; font-weight: 700; fill: #ffffff; }}
    .label {{ font-size: 15px; fill: #d4d6e6; }}
    .value {{ font-size: 17px; font-weight: 700; fill: #3bd2ff; }}
    .dim {{ fill: #9ea2bd; }}
    .note {{ font-size: 12px; fill: #9ea2bd; }}
  </style>
  <rect x="1.5" y="1.5" width="857" height="257" rx="18" fill="url(#bg)" stroke="url(#rim)" stroke-width="3"/>
  <text x="34" y="48" class="title">GitHub at a glance</text>
  <text x="440" y="48" class="title">Languages</text>
  <line x1="414" y1="70" x2="414" y2="222" stroke="#2a3570" stroke-width="2"/>
  {"".join(rows)}
  <g clip-path="url(#bar)">{"".join(bar)}</g>
  {"".join(legend)}
  <text x="826" y="242" class="note" text-anchor="end">Updated {updated}</text>
</svg>
'''


def main():
    repos = own_repos()
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = replace(text, "UPDATED", recently_updated(repos))
    text = replace(text, "PULLS", recent_pull_requests())
    text = replace(text, "STARS", recent_stars())
    readme.write_text(text, encoding="utf-8")
    (ROOT / "assets" / "stats.svg").write_text(stats_card(repos), encoding="utf-8")


if __name__ == "__main__":
    main()
