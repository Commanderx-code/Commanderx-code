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
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:8]

    figures = [("Public projects", len(repos)), ("Releases shipped", releases),
               ("Commits, last 12 months", commits), ("Pull requests merged", merged)]
    rows = []
    for i, (label, value) in enumerate(figures):
        y = 88 + i * 36
        rows.append(f'<text x="34" y="{y}" class="label">{html.escape(label)}</text>'
                    f'<text x="390" y="{y}" class="value" text-anchor="end">{value:,}</text>')

    bar, legend, x = [], [], 445.0
    width = 380.0
    for i, (language, size) in enumerate(top):
        share = size / total
        part = width * share
        color = LANGUAGE_COLORS.get(language, "#9ea2bd")
        bar.append(f'<rect x="{x:.1f}" y="65" width="{part:.1f}" height="8" fill="{color}"/>')
        x += part
        lx, ly = 445 + (i % 2) * 194, 105 + (i // 2) * 29
        legend.append(f'<rect x="{lx}" y="{ly - 9}" width="8" height="8" fill="{color}"/>'
                      f'<text x="{lx + 16}" y="{ly}" class="legend">{html.escape(language)}'
                      f' <tspan class="dim">{share:.0%}</tspan></text>')

    if not legend:
        legend.append('<text x="445" y="105" class="legend">No language data</text>')
    updated = datetime.date.today().strftime("%b %d, %Y").replace(" 0", " ")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="860" height="260" viewBox="0 0 860 260">
  <style>
    text {{ font-family: "Segoe UI", Ubuntu, "Helvetica Neue", Arial, sans-serif; }}
    .heading {{ font-size: 14px; font-weight: 700; letter-spacing: 1.3px; fill: #9fb9b5; }}
    .label {{ font-size: 14px; fill: #cbd3d2; }}
    .value {{ font-family: "DejaVu Sans Mono", monospace; font-size: 17px; font-weight: 700; fill: #f1f4f1; }}
    .legend {{ font-size: 13px; fill: #dce3e0; }}
    .dim {{ fill: #93a3a2; }}
    .note {{ font-size: 11px; fill: #859694; }}
  </style>
  <rect x="0.5" y="0.5" width="859" height="259" rx="5" fill="#111920" stroke="#394b4c"/>
  <text x="34" y="40" class="heading">PUBLIC WORK</text>
  <text x="445" y="40" class="heading">LANGUAGES BY CODE SIZE</text>
  <line x1="34" y1="52" x2="826" y2="52" stroke="#394b4c"/>
  <line x1="420" y1="65" x2="420" y2="213" stroke="#394b4c"/>
  {"".join(rows)}
  <rect x="445" y="65" width="{width:.0f}" height="8" fill="#3a484c"/>
  {"".join(bar)}
  {"".join(legend)}
  <line x1="34" y1="225" x2="826" y2="225" stroke="#394b4c"/>
  <text x="34" y="245" class="note">Repo, release and language totals exclude forks</text>
  <text x="826" y="245" class="note" text-anchor="end">Updated {updated}</text>
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
