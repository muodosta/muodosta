#!/usr/bin/env python3
"""Генерирует анимированную neofetch-подобную карточку профиля GitHub (dark/light SVG)

Данные берутся из GitHub REST API, внешние сервисы не нужны
Анимация (набор команды, построчное появление, рост полос) — чистый CSS внутри SVG.

Запуск:         python scripts/gen_profile.py --user muodosta --out assets --private
Превью офлайн:  python scripts/gen_profile.py --demo --out assets
Без анимации:   добавить --static
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
    "stack": "python · c# · postgresql · docker",
    "now": "proxies & server utilities",
}
COMMAND = "neofetch"
MAX_LANGS = 6
# Языки, которые не нужно показывать (разметка, конфиги и т.п.)
EXCLUDE_LANGS = {"HTML", "CSS", "Jupyter Notebook", "Dockerfile"}

THEMES = {
    "dark": dict(bg="#0d1117", border="#30363d", fg="#c9d1d9", dim="#8b949e",
                 key="#58a6ff", accent="#3fb950", track="#21262d"),
    "light": dict(bg="#ffffff", border="#d0d7de", fg="#24292f", dim="#57606a",
                  key="#0969da", accent="#1a7f37", track="#eaeef2"),
}

# Пиксель-арт 11x8 (отсылка к статусу 👾).
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

# Тайминги анимации, секунды
TYPE_START, TYPE_STEP = 0.4, 0.09   # старт набора команды и пауза между символами
LINE_STEP = 0.14                    # пауза между строками информации

CSS = """
.ln{animation:fade .4s ease-out var(--d) backwards}
.px{animation:pop .25s ease-out var(--d) backwards}
.ch{animation:typed .01s step-end var(--d) backwards}
.bar{transform-box:fill-box;transform-origin:left center;animation:grow .9s cubic-bezier(.2,.7,.2,1) var(--d) backwards}
.cur{animation:blink 1.1s step-end var(--d) infinite}
@keyframes fade{from{opacity:0;transform:translateX(-8px)}}
@keyframes pop{from{opacity:0}}
@keyframes typed{from{fill-opacity:0}}
@keyframes grow{from{transform:scaleX(0)}}
@keyframes blink{from,to{fill-opacity:1}50%{fill-opacity:0}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""


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


def render(stats: dict, theme: str, animate: bool = True) -> str:
    c = THEMES[theme]
    user = escape(stats["user"])
    x_info, x_val, w = 300, 410, 820
    out: list[str] = []

    def group(delay: float, *items: str, cls: str = "ln") -> None:
        """Элементы, которые появляются вместе, начиная с момента delay."""
        if animate:
            out.append(f'<g class="{cls}" style="--d:{delay:.2f}s">{"".join(items)}</g>')
        else:
            out.append("".join(items))

    def text(x, y, content, fill, weight="normal") -> str:
        return (f'<text x="{x}" y="{y}" fill="{fill}" font-weight="{weight}">'
                f'{escape(content)}</text>')

    # Окно и заголовок (видны сразу)
    out.append(f'<rect x="0.5" y="0.5" width="{w - 1}" height="HEIGHT" rx="10" '
               f'fill="{c["bg"]}" stroke="{c["border"]}"/>')
    for i, color in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        out.append(f'<circle cx="{22 + i * 20}" cy="20" r="6" fill="{color}"/>')
    out.append(f'<text x="{w // 2}" y="24" fill="{c["dim"]}" text-anchor="middle" '
               f'font-size="12">{user}@github: ~</text>')

    # Первая команда: символы «набираются» по одному
    chars = "".join(
        f'<tspan class="ch" style="--d:{TYPE_START + i * TYPE_STEP:.2f}s">{escape(ch)}</tspan>'
        if animate else escape(ch)
        for i, ch in enumerate(COMMAND)
    )
    out.append(f'<text x="40" y="66"><tspan fill="{c["accent"]}">{user}@github</tspan>'
               f'<tspan fill="{c["dim"]}">:~$ </tspan><tspan fill="{c["fg"]}">{chars}</tspan></text>')

    t = TYPE_START + len(COMMAND) * TYPE_STEP + 0.25  # момент, когда команда «выполнилась»

    # Пиксель-арт: строки появляются сверху вниз
    px = 15
    for row, line in enumerate(INVADER):
        cells = [f'<rect x="{50 + col * px}" y="{112 + row * px}" width="{px - 1}" '
                 f'height="{px - 1}" fill="{c["accent"]}"/>'
                 for col, ch in enumerate(line) if ch == "#"]
        group(t + row * 0.07, *cells, cls="px")

    # Заголовок блока информации
    y = 108
    header = (f'<text x="{x_info}" y="{y}" font-weight="bold"><tspan fill="{c["accent"]}">{user}</tspan>'
              f'<tspan fill="{c["dim"]}">@</tspan><tspan fill="{c["accent"]}">github</tspan></text>'
              f'<rect x="{x_info}" y="{y + 9}" width="{len(stats["user"]) * 8.4 + 8.4 * 7:.0f}" '
              f'height="1" fill="{c["border"]}"/>')
    group(t, header)
    t += LINE_STEP

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
        group(t, text(x_info, y, key, c["key"], "bold"), text(x_val, y, value, c["fg"]))
        t += LINE_STEP
        y += 24

    # Языки: подпись, затем строки с растущими полосами
    langs = stats["langs"].most_common(MAX_LANGS)
    total = sum(stats["langs"].values()) or 1
    if langs:
        y += 12
        group(t, text(x_info, y, "languages", c["key"], "bold"))
        t += LINE_STEP
        y += 24
        bar_w = 200
        for name, size in langs:
            share = size / total
            group(t, text(x_info, y, name, c["fg"]),
                  f'<rect x="{x_val}" y="{y - 10}" width="{bar_w}" height="10" rx="2" fill="{c["track"]}"/>',
                  text(x_val + bar_w + 12, y, f"{share * 100:.0f}%", c["dim"]))
            bar = (f'<rect x="{x_val}" y="{y - 10}" width="{max(share * bar_w, 2):.1f}" height="10" '
                   f'rx="2" fill="{c["accent"]}"/>')
            group(t + 0.15, bar, cls="bar")
            t += LINE_STEP
            y += 24

    # Цветовая палитра, как в neofetch
    y += 6
    palette = "".join(
        f'<rect x="{x_info + i * 26}" y="{y}" width="22" height="14" rx="2" fill="{color}"/>'
        for i, color in enumerate(("#ff5f56", "#ffbd2e", "#27c93f", c["key"], "#bc8cff", "#39c5cf", c["fg"], c["dim"]))
    )
    group(t, palette)
    t += LINE_STEP * 2

    # Финальный промпт: курсор мигает после завершения всей «загрузки»
    y += 52
    cursor = (f'<tspan class="cur" fill="{c["fg"]}">█</tspan>' if animate
              else f'<tspan fill="{c["fg"]}">█</tspan>')
    group(t, f'<text x="40" y="{y}"><tspan fill="{c["accent"]}">{user}@github</tspan>'
             f'<tspan fill="{c["dim"]}">:~$ </tspan>{cursor}</text>')

    height = y + 28
    body = "\n  ".join(out).replace('height="HEIGHT"', f'height="{height - 1}"')
    style = f"<style>{CSS}</style>\n  " if animate else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{height}" '
            f'viewBox="0 0 {w} {height}" font-family="{FONT}" font-size="14" role="img" '
            f'aria-label="{user} GitHub profile">\n  {style}{body}\n</svg>\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="muodosta")
    parser.add_argument("--out", default="assets")
    parser.add_argument("--demo", action="store_true", help="данные-заглушки, без сети")
    parser.add_argument("--private", action="store_true", help="учитывать приватные репозитории")
    parser.add_argument("--static", action="store_true", help="без анимации")
    args = parser.parse_args()

    token = os.getenv("STATS_TOKEN") or os.getenv("GITHUB_TOKEN")
    stats = demo_stats(args.user) if args.demo else fetch_stats(args.user, token, args.private)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        svg = render(stats, theme, animate=not args.static)
        (out_dir / f"profile-{theme}.svg").write_text(svg, encoding="utf-8")
        print(f"written {out_dir / f'profile-{theme}.svg'}")


if __name__ == "__main__":
    main()