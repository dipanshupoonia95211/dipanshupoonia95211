#!/usr/bin/env python3
"""Scrape the public GitHub contribution calendar -- no token, no GraphQL.

GitHub serves the same calendar fragment the profile page uses at
    https://github.com/users/<username>/contributions
It is public HTML, so all we need is requests + a parser.

Writes data/contributions.json:  raw days + derived stats.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

USERNAME = os.environ.get("GH_USERNAME", "dipanshupoonia95211")
URL = f"https://github.com/users/{USERNAME}/contributions"
OUT = Path(__file__).resolve().parent.parent / "data" / "contributions.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (profile-art bot; +https://github.com/%s)" % USERNAME,
    "Accept": "text/html",
    "X-Requested-With": "XMLHttpRequest",
}

# "5 contributions on September 3rd." / "No contributions on August 31st."
_COUNT_RE = re.compile(r"^\s*(No|[\d,]+)\s+contribution", re.I)


def fetch_html() -> str:
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def _count_from_tooltip(text: str) -> int:
    m = _COUNT_RE.match(text or "")
    if not m:
        return 0
    tok = m.group(1)
    return 0 if tok.lower() == "no" else int(tok.replace(",", ""))


def parse_bs4(html: str) -> list[dict]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # The per-day count lives in a sibling <tool-tip for="<cell id>">, not on the cell.
    tips: dict[str, int] = {}
    for tip in soup.find_all("tool-tip"):
        target = tip.get("for")
        if target:
            tips[target] = _count_from_tooltip(tip.get_text())

    days = []
    for cell in soup.select("td.ContributionCalendar-day"):
        iso = cell.get("data-date")
        if not iso:
            continue
        days.append(
            {
                "date": iso,
                "count": tips.get(cell.get("id", ""), 0),
                "level": int(cell.get("data-level") or 0),
            }
        )
    return days


def parse_regex(html: str) -> list[dict]:
    """Dependency-free fallback if bs4 is unavailable or GitHub tweaks the markup."""
    tips = {
        m.group(1): _count_from_tooltip(m.group(2))
        for m in re.finditer(r'<tool-tip[^>]*\sfor="([^"]+)"[^>]*>(.*?)</tool-tip>', html, re.S)
    }
    days = []
    for m in re.finditer(r"<td[^>]*class=\"[^\"]*ContributionCalendar-day[^\"]*\"[^>]*>", html):
        tag = m.group(0)
        iso = re.search(r'data-date="([^"]+)"', tag)
        if not iso:
            continue
        cid = re.search(r'id="([^"]+)"', tag)
        lvl = re.search(r'data-level="(\d+)"', tag)
        days.append(
            {
                "date": iso.group(1),
                "count": tips.get(cid.group(1) if cid else "", 0),
                "level": int(lvl.group(1)) if lvl else 0,
            }
        )
    return days


def compute_stats(days: list[dict]) -> dict:
    today = date.today()
    # The current week is padded with future cells; they are not real zero-days.
    days = [d for d in days if datetime.strptime(d["date"], "%Y-%m-%d").date() <= today]
    days.sort(key=lambda d: d["date"])
    by_date = {d["date"]: d["count"] for d in days}

    total = sum(by_date.values())
    active = sum(1 for c in by_date.values() if c > 0)

    # Longest streak
    longest = run = 0
    prev: date | None = None
    for d in days:
        cur = datetime.strptime(d["date"], "%Y-%m-%d").date()
        if d["count"] > 0 and prev is not None and (cur - prev).days == 1:
            run += 1
        elif d["count"] > 0:
            run = 1
        else:
            run = 0
        longest = max(longest, run)
        prev = cur

    # Current streak: an empty *today* does not break it (the day isn't over).
    cursor = today
    if by_date.get(cursor.isoformat(), 0) == 0:
        cursor -= timedelta(days=1)
    current = 0
    while by_date.get(cursor.isoformat(), 0) > 0:
        current += 1
        cursor -= timedelta(days=1)

    best = max(days, key=lambda d: d["count"], default={"date": None, "count": 0})

    monthly: dict[str, int] = defaultdict(int)
    for d in days:
        monthly[d["date"][:7]] += d["count"]

    return {
        "username": USERNAME,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + "Z",
        "range": {"start": days[0]["date"], "end": days[-1]["date"]} if days else {},
        "total": total,
        "active_days": active,
        "current_streak": current,
        "longest_streak": longest,
        "best_day": {"date": best["date"], "count": best["count"]},
        "max_day": best["count"],
        "monthly": dict(sorted(monthly.items())),
        "days": days,
    }


def sanity_check(stats: dict, prev: dict | None) -> str | None:
    """Refuse to overwrite a good calendar with a broken scrape.

    The failure mode this guards against: GitHub restructures the markup so the
    <td> cells still parse but the counts all come back 0. That would silently
    commit a blank heatmap over a good one. A real rolling window only sheds
    about one day at a time, so a collapse to zero is always a parser bug.
    """
    if not prev:
        return None
    old_total = prev.get("total", 0)
    if old_total >= 10 and stats["total"] == 0:
        return f"parsed 0 contributions but the previous run had {old_total}"
    if old_total >= 20 and stats["total"] < old_total * 0.4:
        return f"total collapsed {old_total} -> {stats['total']}"
    if prev.get("active_days", 0) >= 5 and stats["active_days"] == 0:
        return "parsed 0 active days"
    return None


def main() -> int:
    prev = None
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - a corrupt cache just means no baseline
            prev = None

    html = fetch_html()
    try:
        days = parse_bs4(html)
    except Exception as exc:  # noqa: BLE001 - fall back rather than fail the cron
        print(f"bs4 parse failed ({exc}); using regex fallback", file=sys.stderr)
        days = []
    if not days:
        days = parse_regex(html)
    if not days:
        print("ERROR: parsed 0 day cells -- GitHub markup may have changed", file=sys.stderr)
        return 1

    stats = compute_stats(days)

    problem = sanity_check(stats, prev)
    if problem and os.environ.get("ALLOW_REGRESSION") != "1":
        print(f"ERROR: refusing to overwrite {OUT.name} -- {problem}.\n"
              f"       The scraper is probably broken; the committed heatmap is "
              f"left untouched.\n"
              f"       Set ALLOW_REGRESSION=1 if the drop is genuine.",
              file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(
        f"{OUT.name}: {len(stats['days'])} days, {stats['total']} contributions, "
        f"streak {stats['current_streak']} (longest {stats['longest_streak']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
