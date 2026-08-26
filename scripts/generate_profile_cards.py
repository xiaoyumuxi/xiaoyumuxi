#!/usr/bin/env python3

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape


API_ROOT = "https://api.github.com"
LANGUAGE_COLORS = {
    "C": "#A8B9CC",
    "C#": "#512BD4",
    "C++": "#00599C",
    "CSS": "#1572B6",
    "Go": "#00ADD8",
    "HTML": "#E34F26",
    "Java": "#ED8B00",
    "JavaScript": "#F7DF1E",
    "Kotlin": "#7F52FF",
    "Lua": "#2C2D72",
    "Python": "#3776AB",
    "Rust": "#DEA584",
    "Shell": "#89E051",
    "Swift": "#F05138",
    "TypeScript": "#3178C6",
    "Vue": "#42B883",
}
LANGUAGE_EXCLUDED_REPOS = {
    "30daymakeos",
    "cc-switch",
    "chatlog_alpha",
    "claude-code-source-code",
    "first-contributions",
    "firstcontributions",
    "interview-guide",
    "notionnext",
    "thaw",
    "weflow",
    "wechat-mac-reader",
}


def github_get(path, token=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "xiaoyumuxi-profile-card-generator",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(f"{API_ROOT}{path}", headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API returned {error.code} for {path}: {details}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach GitHub API for {path}: {error.reason}") from error


def github_search_count(query, token=None):
    params = urlencode({"q": query, "per_page": 1})
    result = github_get(f"/search/issues?{params}", token)
    return result["total_count"]


def collect_profile(username, token=None):
    user = github_get(f"/users/{username}", token)
    repos = github_get(f"/users/{username}/repos?type=owner&sort=updated&per_page=100", token)
    owned_repos = [repo for repo in repos if not repo["fork"] and repo["owner"]["login"].lower() == username.lower()]

    languages = {}
    language_repos = [repo for repo in owned_repos if repo["name"].lower() not in LANGUAGE_EXCLUDED_REPOS]
    for repo in language_repos:
        repo_languages = github_get(f"/repos/{username}/{repo['name']}/languages", token)
        for language, size in repo_languages.items():
            languages[language] = languages.get(language, 0) + size

    pull_requests_opened = github_search_count(f"is:pr author:{username}", token)
    pull_requests_merged = github_search_count(f"is:pr author:{username} is:merged", token)
    pull_requests_reviewed = github_search_count(f"is:pr reviewed-by:{username} -author:{username}", token)

    return {
        "name": user.get("name") or username,
        "username": username,
        "public_repos": user["public_repos"],
        "followers": user["followers"],
        "stars": sum(repo["stargazers_count"] for repo in owned_repos),
        "pull_requests_opened": pull_requests_opened,
        "pull_requests_merged": pull_requests_merged,
        "pull_requests_reviewed": pull_requests_reviewed,
        "since": user["created_at"][:4],
        "languages": languages,
    }


def format_number(value):
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}m"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)


def svg_shell(body, title, description, width=495, height=195):
    return f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">{escape(title)}</title>
  <desc id="desc">{escape(description)}</desc>
  <defs>
    <linearGradient id="card" x1="0" y1="0" x2="{width}" y2="{height}" gradientUnits="userSpaceOnUse">
      <stop stop-color="#0B1020"/>
      <stop offset="1" stop-color="#172554"/>
    </linearGradient>
    <linearGradient id="line" x1="28" y1="0" x2="360" y2="0" gradientUnits="userSpaceOnUse">
      <stop stop-color="#2DD4BF"/>
      <stop offset="0.55" stop-color="#58A6FF"/>
      <stop offset="1" stop-color="#A78BFA"/>
    </linearGradient>
  </defs>
  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="15" fill="url(#card)" stroke="#334155" stroke-width="2"/>
  {body}
</svg>
'''


def render_stats(profile):
    stats = [
        ("REPOSITORIES", profile["public_repos"]),
        ("STARS EARNED", profile["stars"]),
        ("PRS OPENED", profile["pull_requests_opened"]),
        ("PRS MERGED", profile["pull_requests_merged"]),
        ("PRS REVIEWED", profile["pull_requests_reviewed"]),
        ("FOLLOWERS", profile["followers"]),
    ]
    stat_blocks = []
    for index, (label, value) in enumerate(stats):
        column = index % 3
        row = index // 3
        x = 30 + column * 153
        y = 91 + row * 58
        stat_blocks.append(
            f'<text x="{x}" y="{y}" fill="#F8FAFC" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="25" font-weight="700">{format_number(value)}</text>'
            f'<text x="{x}" y="{y + 20}" fill="#94A3B8" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="9" font-weight="600" letter-spacing="1">{label}</text>'
        )

    body = f'''
  <text x="28" y="37" fill="#F8FAFC" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="18" font-weight="700">GitHub signals</text>
  <text x="467" y="36" text-anchor="end" fill="#64748B" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="11">since {profile['since']}</text>
  <rect x="28" y="52" width="326" height="3" rx="1.5" fill="url(#line)"/>
  {''.join(stat_blocks)}'''
    return svg_shell(body, f"{profile['name']}'s GitHub statistics", "Public repositories, stars, pull requests opened, merged and reviewed, and followers")


def render_languages(profile):
    sorted_languages = sorted(profile["languages"].items(), key=lambda item: item[1], reverse=True)[:6]
    total = sum(size for _, size in sorted_languages)

    if total == 0:
        sorted_languages = [("No language data", 1)]
        total = 1

    segments = []
    labels = []
    offset = 28.0
    bar_width = 439.0
    for index, (language, size) in enumerate(sorted_languages):
        percentage = size / total
        width = bar_width * percentage
        color = LANGUAGE_COLORS.get(language, "#94A3B8")
        segments.append(f'<rect x="{offset:.2f}" y="58" width="{width:.2f}" height="10" fill="{color}"/>')
        offset += width

        column = index % 2
        row = index // 2
        x = 30 + column * 225
        y = 98 + row * 34
        labels.append(
            f'<circle cx="{x + 5}" cy="{y - 4}" r="5" fill="{color}"/>'
            f'<text x="{x + 18}" y="{y}" fill="#CBD5E1" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="12" font-weight="600">{escape(language)}</text>'
            f'<text x="{x + 190}" y="{y}" text-anchor="end" fill="#64748B" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="11">{percentage * 100:.1f}%</text>'
        )

    body = f'''
  <text x="28" y="37" fill="#F8FAFC" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="18" font-weight="700">Code footprint</text>
  <text x="467" y="36" text-anchor="end" fill="#64748B" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="11">owned public repos</text>
  <clipPath id="bar"><rect x="28" y="58" width="439" height="10" rx="5"/></clipPath>
  <g clip-path="url(#bar)">{''.join(segments)}</g>
  {''.join(labels)}'''
    return svg_shell(body, f"{profile['name']}'s most-used languages", "Language distribution across owned public repositories")


def write_if_changed(path, content):
    if path.exists() and path.read_text(encoding="utf-8") == content:
        print(f"Unchanged: {path}")
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Updated: {path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate self-hosted SVG cards for a GitHub profile README.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--output-dir", default="profile")
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN")
    profile = collect_profile(args.username, token)
    output_dir = Path(args.output_dir)

    write_if_changed(output_dir / "stats.svg", render_stats(profile))
    write_if_changed(output_dir / "top-langs.svg", render_languages(profile))


if __name__ == "__main__":
    main()
