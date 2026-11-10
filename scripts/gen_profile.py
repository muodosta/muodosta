#!/usr/bin/env python3
"""Генерирует neofetch-подобную карточку профиля GitHub (тёмная и светлая SVG)

Данные берутся из GitHub REST API, внешние сервисы не нужны
Запуск:  python scripts/gen_profile.py --user muodosta --out assets
Превью без сети:  python scripts/gen_profile.py --demo --out assets
"""
import argparse
import json
import os
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path

# Статичные поля карточки
CONFIG = {
    "role": "backend / devops",
    "stack": "python · postgresql · docker",
    "now": "proxies & server utilities",
}
MAX_LANGS = 4
# Языки, которые не нужно показывать (разметка, конфиги и т.п.)
EXCLUDE_LANGS = {"HTML", "CSS", "Jupyter Notebook", "Dockerfile"}

THEMES = {
    "dark": dict(bg="#0d1117", border="#30363d", fg="#c9d1d9", dim="#8b949e",
                 key="#58a6ff", accent="#3fb950", track="#21262d"),
    "light": dict(bg="#ffffff", border="#d0d7de", fg="#24292f", dim="#57606a",
                  key="#0969da", accent="#1a7f37", track="#eaeef2"),
}

# Пиксель-арт 11x8
INVADER = [
    "  #     #  ",
    "   #   #   ",
    "  #######  ",
    " ## ### ## ",
    "###########",
    "# ####### #",
    "# #     # #",
    "   ## ##   ",
]

FONT = ("ui-monospace, SFMono-Regular, 'JetBrains Mono', 'Fira Code', "
        "Consolas, 'Liberation Mono', Menlo, monospace")
API = "https://api.github.com"


def api(path: str, token: str | None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-card"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_stats(user: str, token: str | None, private: bool = False) -> dict:
    profile = api(f"/users/{user}", token)
    if private:  # нужен токен с доступом к приватным репозиториям
        path = "/user/repos?per_page=100&affiliation=owner&visibility=all"
    else:
        path = f"/users/{user}/repos?per_page=100&type=owner"
    repos, page = [], 1
    while True:
        chunk = api(f"{path}&page={page}", token)
        repos += chunk
        if len(chunk) < 100:
            break
        page += 1
    own = [r for r in repos if not r["fork"]]
    langs = Counter()
    for repo in own:
        langs.update(api(f"/repos/{repo['full_name']}/languages", token))
    for name in EXCLUDE_LANGS:
        langs.pop(name, None)
    return {
        "user": user,
        "created": profile["created_at"],
        "followers": profile["followers"],
        "own": len(own),
        "forks": len(repos) - len(own),
        "stars": sum(r["stargazers_count"] for r in own),
        "langs": langs,
    }


def demo_stats(user: str) -> dict:
    return {"user": user, "created": "2022-03-02T00:00:00Z", "followers": 9,
            "own": 2, "forks": 2, "stars": 0,
            "langs": Counter({"Python": 6200, "Shell": 3800})}


def uptime(created: str) -> str:
    start = datetime.fromisoformat(created.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    months = (now.year - start.year) * 12 + now.month - start.month
    years, months = divmod(max(months, 0), 12)
    return f"{years}y {months}m"


def render(stats: dict, theme: str) -> str:
    c = THEMES[theme]
    user = escape(stats["user"])
    x_info, x_val, w = 300, 410, 820
    out = []

    def text(x, y, content, fill, weight="normal"):
        out.append(f'<text x="{x}" y="{y}" fill="{fill}" font-weight="{weight}">'
                   f'{escape(content)}</text>')

    # Окно и заголовок
    out.append(f'<rect x="0.5" y="0.5" width="{w - 1}" height="HEIGHT" rx="10" '
               f'fill="{c["bg"]}" stroke="{c["border"]}"/>')
    for i, color in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        out.append(f'<circle cx="{22 + i * 20}" cy="20" r="6" fill="{color}"/>')
    out.append(f'<text x="{w // 2}" y="24" fill="{c["dim"]}" text-anchor="middle" '
               f'font-size="12">{user}@github: ~</text>')

    # Первая команда
    out.append(f'<text x="40" y="66"><tspan fill="{c["accent"]}">{user}@github</tspan>'
               f'<tspan fill="{c["dim"]}">:~$ </tspan><tspan fill="{c["fg"]}">neofetch</tspan></text>')

    # Пиксель-арт
    px = 15
    for row, line in enumerate(INVADER):
        for col, ch in enumerate(line):
            if ch == "#":
                out.append(f'<rect x="{50 + col * px}" y="{112 + row * px}" width="{px - 1}" '
                           f'height="{px - 1}" fill="{c["accent"]}"/>')

    # Заголовок блока информации
    y = 108
    out.append(f'<text x="{x_info}" y="{y}" font-weight="bold"><tspan fill="{c["accent"]}">{user}</tspan>'
               f'<tspan fill="{c["dim"]}">@</tspan><tspan fill="{c["accent"]}">github</tspan></text>')
    out.append(f'<rect x="{x_info}" y="{y + 9}" width="{len(stats["user"]) * 8.4 + 8.4 * 7:.0f}" '
               f'height="1" fill="{c["border"]}"/>')

    rows = [
        ("role", CONFIG["role"]),
        ("stack", CONFIG["stack"]),
        ("now", CONFIG["now"]),
        ("uptime", uptime(stats["created"])),
        ("repos", f'{stats["own"] + stats["forks"]} ({stats["own"]} own, {stats["forks"]} forks)'),
        ("stars", str(stats["stars"])),
        ("followers", str(stats["followers"])),
    ]
    y += 34
    for key, value in rows:
        text(x_info, y, key, c["key"], "bold")
        text(x_val, y, value, c["fg"])
        y += 24

    # Языки
    langs = stats["langs"].most_common(MAX_LANGS)
    total = sum(stats["langs"].values()) or 1
    if langs:
        y += 12
        text(x_info, y, "languages", c["key"], "bold")
        y += 24
        bar_w = 200
        for name, size in langs:
            share = size / total
            text(x_info, y, name, c["fg"])
            out.append(f'<rect x="{x_val}" y="{y - 10}" width="{bar_w}" height="10" rx="2" fill="{c["track"]}"/>')
            out.append(f'<rect x="{x_val}" y="{y - 10}" width="{max(share * bar_w, 2):.1f}" height="10" '
                       f'rx="2" fill="{c["accent"]}"/>')
            text(x_val + bar_w + 12, y, f"{share * 100:.0f}%", c["dim"])
            y += 24

    # Цветовая палитра, как в neofetch
    y += 6
    for i, color in enumerate(("#ff5f56", "#ffbd2e", "#27c93f", c["key"], "#bc8cff", "#39c5cf", c["fg"], c["dim"])):
        out.append(f'<rect x="{x_info + i * 26}" y="{y}" width="22" height="14" rx="2" fill="{color}"/>')

    # Финальный промпт с мигающим курсором
    y += 52
    out.append(f'<text x="40" y="{y}"><tspan fill="{c["accent"]}">{user}@github</tspan>'
               f'<tspan fill="{c["dim"]}">:~$ </tspan></text>')
    cursor_x = 40 + (len(stats["user"]) + 7 + 3) * 8.4
    out.append(f'<rect x="{cursor_x:.1f}" y="{y - 12}" width="8" height="15" fill="{c["fg"]}">'
               f'<animate attributeName="opacity" values="1;0" dur="1.1s" calcMode="discrete" '
               f'repeatCount="indefinite"/></rect>')

    height = y + 28
    body = "\n  ".join(out).replace('height="HEIGHT"', f'height="{height - 1}"')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{height}" '
            f'viewBox="0 0 {w} {height}" font-family="{FONT}" font-size="14" role="img" '
            f'aria-label="{user} GitHub profile">\n  {body}\n</svg>\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="muodosta")
    parser.add_argument("--out", default="assets")
    parser.add_argument("--demo", action="store_true", help="данные-заглушки, без сети")
    parser.add_argument("--private", action="store_true", help="учитывать приватные репозитории")
    args = parser.parse_args()

    token = os.getenv("STATS_TOKEN") or os.getenv("GITHUB_TOKEN")
    stats = demo_stats(args.user) if args.demo else fetch_stats(args.user, token, args.private)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (out_dir / f"profile-{theme}.svg").write_text(render(stats, theme), encoding="utf-8")
        print(f"written {out_dir / f'profile-{theme}.svg'}")


if __name__ == "__main__":
    main()