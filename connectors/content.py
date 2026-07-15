"""
Content connector — assembles the day's post DRAFT. Never posts anything.
========================================================================
On a scheduled day (default Mon/Wed/Fri) it pulls the next queued post and
renders a copy-paste-ready caption + carousel outline. Publishing stays manual
or via a ToS-compliant scheduler — an agent must NOT auto-post to LinkedIn.

Rules honoured: MYNA is the only nameable brand; clients stay anonymised.
"""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path

WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _load(cfg_path: Path) -> dict:
    try:
        return json.loads(cfg_path.read_text())
    except Exception:
        return {}


def todays_draft(cfg_path: Path, today: dt.date | None = None) -> dict:
    cfg = _load(cfg_path)
    today = today or dt.datetime.now(dt.timezone.utc).date()
    sched = [WEEKDAYS[d.lower()[:3]] for d in cfg.get("schedule", ["mon", "wed", "fri"])
             if d.lower()[:3] in WEEKDAYS]
    queue = cfg.get("queue", [])
    is_post_day = today.weekday() in sched
    if not is_post_day:
        nxt = _next_day(today, sched)
        return {"post_day": False, "next": nxt.strftime("%A %d %b")}
    # pick the first undrafted item
    idx = next((i for i, p in enumerate(queue) if not p.get("_drafted")), None)
    if idx is None:
        return {"post_day": True, "empty": True}
    post = queue[idx]
    return {"post_day": True, "index": idx, "post": post,
            "rendered": _render(post)}


def _next_day(today: dt.date, sched: list[int]) -> dt.date:
    for i in range(1, 8):
        d = today + dt.timedelta(days=i)
        if d.weekday() in sched:
            return d
    return today


def _render(post: dict) -> str:
    hook = post.get("hook", "")
    doubt = post.get("doubt_targeted", "")
    body = post.get("body", "")
    cta = post.get("cta", "")
    slides = post.get("carousel", [])
    out = [f"HOOK:\n{hook}", ""]
    if doubt:
        out += [f"(Doubt being subtracted: {doubt})", ""]
    out += [f"BODY:\n{body}", "", f"CTA:\n{cta}", "", "CAROUSEL (10-slide, black matte-glass):"]
    for i, s in enumerate(slides, 1):
        out.append(f"  {i:>2}. {s}")
    if not slides:
        out.append("  (no carousel outline in queue for this post)")
    return "\n".join(out)
