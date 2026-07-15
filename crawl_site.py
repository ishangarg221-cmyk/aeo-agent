#!/usr/bin/env python3
"""
crawl_site.py — audit every page in the sitemap, not just the homepage.
=======================================================================
Reads the store's sitemap.xml (Shopify auto-generates it), collects every
product / collection / page / article URL, and scores each one for AI-citation
readiness. Domain-level checks (AI-bot crawlability, llms.txt) run ONCE and apply
to all pages; page-level checks (schema, answer blocks, extractability, meta) run
per URL.

Two cadences (chosen by the workflow):
    --mode daily    audit the priority pages only (fast, every morning)
    --mode weekly   audit the whole sitemap (full picture, once a week)

Writes crawl-results.json, which build_dashboard.py turns into the two-tier
dashboard (site overview + per-page drill-down).

Usage:
    python crawl_site.py --mode daily
    python crawl_site.py --mode weekly --config myna.config.json
"""
from __future__ import annotations
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8"); _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse, datetime as dt, json, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

HERE = Path(__file__).resolve().parent
_sys.path.insert(0, str(HERE))
import aeo_agent as A
from bs4 import BeautifulSoup

MAX_PAGES = 600           # hard cap so a huge store can't run away
WORKERS = 6               # polite concurrency
DAILY_DEFAULT = 20        # top-N pages when no priority list is given


def load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# ----------------------------------------------------------- sitemap parsing
def _locs(xml: str) -> list[str]:
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml or "", re.I)


def collect_urls(base: str) -> list[dict]:
    """Return [{url, type}] from the sitemap index (one level of children)."""
    root = A.get_text(urljoin(base, "/sitemap.xml"))
    if not root:
        return []
    urls, seen = [], set()
    locs = _locs(root)
    children = [l for l in locs if ".xml" in l.lower()]
    pages = [l for l in locs if ".xml" not in l.lower()]
    for child in children:
        body = A.get_text(child)
        if body:
            pages.extend(l for l in _locs(body) if ".xml" not in l.lower())
    for u in pages:
        if u in seen:
            continue
        seen.add(u)
        urls.append({"url": u, "type": _classify(u)})
        if len(urls) >= MAX_PAGES:
            break
    return urls


def _classify(u: str) -> str:
    p = urlparse(u).path.lower()
    if "/products/" in p:
        return "product"
    if "/collections/" in p:
        return "collection"
    if "/blogs/" in p or "/blog/" in p:
        return "article"
    if "/pages/" in p or "/policies/" in p:
        return "page"
    if p in ("", "/"):
        return "home"
    return "other"


# ------------------------------------------------------------- audit a page
def audit_page(url: str, base: str, domain_sections: dict, brand: str) -> dict:
    resp = A.fetch(url)
    if not hasattr(resp, "status_code") or resp.status_code != 200:
        code = getattr(resp, "status_code", "unreachable")
        return {"url": url, "score": None, "error": str(code)}
    soup = BeautifulSoup(resp.text, "html.parser")
    page_sections = {
        "Structured data / schema": A.check_schema(soup),
        "Answer structure": A.check_answer_structure(soup, resp.text),
        "Content extractability": A.check_extractability(soup, resp.text),
        "Meta & entity signals": A.check_meta_entity(soup, base),
    }
    sections = {**domain_sections, **page_sections}
    total = sum(s["score"] for s in sections.values())
    maxt = sum(s["max"] for s in sections.values())
    pct = round(total / maxt * 100)
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    fixes = sorted((f for s in sections.values() for f in s["fixes"]),
                   key=lambda x: order.get(x[0], 9))
    return {"url": url, "score": pct, "grade": A.grade(pct), "ranked_fixes": fixes}


# ------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--mode", choices=["daily", "weekly"], default="daily")
    a = ap.parse_args()
    cfg = load(Path(a.config or (HERE / "myna.config.json"))) or _sys.exit("config not found")
    url0 = cfg["url"]
    base = f"{urlparse(url0).scheme}://{urlparse(url0).netloc}"
    brand, domain = cfg["brand"], cfg["domain"]

    print(f"[{a.mode}] reading sitemap for {domain} …")
    all_urls = collect_urls(base)
    if not all_urls:
        # fall back to just the homepage if no sitemap
        all_urls = [{"url": url0, "type": "home"}]
    print(f"  found {len(all_urls)} URLs in sitemap")

    # choose the working set by mode
    if a.mode == "daily":
        priority = cfg.get("priority_pages") or []
        if priority:
            working = [{"url": u, "type": _classify(u)} for u in priority]
        else:
            # homepage + first N (sitemap tends to list important pages first)
            working = all_urls[:cfg.get("max_daily", DAILY_DEFAULT)]
    else:
        working = all_urls
    print(f"  auditing {len(working)} page(s) this run")

    # domain-level checks ONCE
    domain_sections = {
        "Crawlability (AI bots)": A.check_crawlability(base),
        "llms.txt": A.check_llms_txt(base),
    }

    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(audit_page, w["url"], base, domain_sections, brand): w
                for w in working}
        for fut in as_completed(futs):
            w = futs[fut]
            try:
                r = fut.result()
            except Exception as e:
                r = {"url": w["url"], "score": None, "error": str(e)}
            r["type"] = w["type"]
            results.append(r)

    scored = [r for r in results if isinstance(r.get("score"), (int, float))]
    scored.sort(key=lambda r: r["score"])
    avg = round(sum(r["score"] for r in scored) / len(scored)) if scored else None

    # sitewide issue frequency (which fix shows up on the most pages)
    freq = {}
    for r in scored:
        for sev, text in r.get("ranked_fixes", []):
            key = text.split(".")[0][:80]
            freq.setdefault(key, {"sev": sev, "count": 0})
            freq[key]["count"] += 1
    sitewide = sorted(({"issue": k, **v} for k, v in freq.items()),
                      key=lambda x: -x["count"])[:10]

    out = {
        "brand": brand, "domain": domain, "base": base,
        "mode": a.mode,
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
        "sitemap_total": len(all_urls),
        "audited": len(results), "avg_score": avg,
        "domain_sections": {k: {"score": v["score"], "max": v["max"],
                                "findings": v["findings"], "fixes": v["fixes"]}
                            for k, v in domain_sections.items()},
        "sitewide_issues": sitewide,
        "pages": results,
    }
    (HERE / "crawl-results.json").write_text(json.dumps(out, indent=2, default=str),
                                             encoding="utf-8")
    print(f"  avg score {avg} across {len(scored)} scored pages → crawl-results.json")


if __name__ == "__main__":
    main()
