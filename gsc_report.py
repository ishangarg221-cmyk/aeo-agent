#!/usr/bin/env python3
"""
gsc_report.py — the Search Console agent.
=========================================
Leads with the thing that matters for MYNA right now: WHY pages aren't indexed.
Then: opportunities (striking-distance queries, low-CTR pages, country gaps),
a content plan built from real query data, and sitemap timing advice.

Runs in API mode (service account) or CSV mode (gsc-exports/*.csv). Writes
gsc-results.json for the dashboard, and prints a readable summary.

Usage:
    python gsc_report.py                      # MYNA
    python gsc_report.py --inspect 100        # inspect up to N URLs' index status
    python gsc_report.py --submit-sitemap https://artificialjewellers.com/sitemap.xml
"""
from __future__ import annotations
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8"); _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse, datetime as dt, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
_sys.path.insert(0, str(HERE))
from connectors import gsc as G


def load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def url_list(base):
    """URLs to check index status for: crawl results if present, else sitemap."""
    cr = load(HERE / "crawl-results.json")
    if cr and cr.get("pages"):
        return [p["url"] for p in cr["pages"]]
    try:
        import crawl_site
        return [u["url"] for u in crawl_site.collect_urls(base)]
    except Exception:
        return []


def index_diagnosis(client, urls, limit):
    """Inspect up to `limit` URLs, bucket them, and rank the fixes."""
    urls = urls[:limit]
    inspected = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(client.inspect, u): u for u in urls}
        for f in as_completed(futs):
            r = f.result()
            if "_error" not in r:
                inspected.append(r)
    buckets = {"indexed": [], "fix": [], "junk-not-indexed": [], "canonical": [],
               "noindex": [], "robots": [], "remove": [], "ok-skip": [], "review": []}
    for r in inspected:
        bucket, advice = G.advise_coverage(r.get("coverageState"))
        klass = G.classify_url(r["url"])
        if bucket == "indexed":
            buckets["indexed"].append(r["url"])
        elif klass == "junk":
            buckets["junk-not-indexed"].append({"url": r["url"], "state": r.get("coverageState"),
                                                "advice": "Junk/duplicate URL — fine that it's unindexed. noindex or ignore."})
        else:
            key = bucket if bucket in buckets else "review"
            buckets[key].append({"url": r["url"], "state": r.get("coverageState"), "advice": advice})
    return {"inspected": len(inspected), "buckets": buckets}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config"); ap.add_argument("--inspect", type=int, default=60)
    ap.add_argument("--submit-sitemap", metavar="URL")
    a = ap.parse_args()
    cfg = load(Path(a.config or (HERE / "myna.config.json"))) or _sys.exit("config not found")
    prop = cfg.get("gsc_property", "sc-domain:" + cfg["domain"])
    base = f"https://{cfg['domain']}"

    client = G.GSC(prop)
    mode = "api" if client.connected else "csv"
    exports = HERE / "gsc-exports"

    # explicit opt-in sitemap submit
    if a.submit_sitemap:
        print("Submitting sitemap:", client.submit_sitemap(a.submit_sitemap)); return

    # gather analytics (API or CSV)
    if client.connected:
        pages = client.top_pages(); queries = client.top_queries(); countries = client.by_country()
        sitemaps = client.list_sitemaps()
    elif exports.exists():
        csvd = G.from_csv(exports)
        pages, queries, countries = csvd["pages"], csvd["queries"], csvd["countries"]
        sitemaps = []
    else:
        print("No GSC connection and no gsc-exports/*.csv found — nothing to report yet.")
        pages = queries = countries = []; sitemaps = []

    err = next((x for x in (pages, queries, countries) if isinstance(x, dict) and "_error" in x), None)
    if err:
        print("GSC error:", err["_error"])

    opps = G.opportunities(pages or [], queries or [], countries or [])
    plan = G.content_plan(opps["striking_distance"], opps["low_ctr_pages"])

    # index diagnosis (API only)
    diag = None
    if client.connected:
        diag = index_diagnosis(client, url_list(base), a.inspect)

    # sitemap advice
    sm_advice = []
    for sm in sitemaps if isinstance(sitemaps, list) else []:
        if "_error" in sm:
            continue
        last = sm.get("lastDownloaded", "")
        stale = ""
        try:
            d = dt.datetime.fromisoformat(last.replace("Z", "+00:00"))
            if (dt.datetime.now(dt.timezone.utc) - d).days > 14:
                stale = " — not fetched in 14+ days; resubmit."
        except Exception:
            pass
        sm_advice.append({"path": sm.get("path"), "lastDownloaded": last,
                          "errors": sm.get("errors", 0), "warnings": sm.get("warnings", 0),
                          "note": ("Has errors — fix then resubmit." if int(sm.get("errors", 0) or 0) else "OK") + stale})

    out = {
        "brand": cfg["brand"], "domain": cfg["domain"], "property": prop, "mode": mode,
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
        "totals": {"clicks": sum(p["clicks"] for p in pages or []),
                   "impressions": sum(p["impressions"] for p in pages or [])},
        "top_pages": (pages or [])[:15], "top_queries": (queries or [])[:20],
        "countries": (countries or [])[:15], "top_country": opps["top_country"],
        "opportunities": opps, "content_plan": plan,
        "sitemaps": sm_advice, "index": diag,
    }
    (HERE / "gsc-results.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    # console summary
    print(f"\n=== GSC report ({mode} mode) · {cfg['brand']} ===")
    print(f"  clicks {out['totals']['clicks']} · impressions {out['totals']['impressions']}")
    if diag:
        b = diag["buckets"]
        print(f"  index: {len(b['indexed'])} indexed of {diag['inspected']} inspected")
        print(f"    → push these (valuable, not indexed): {len(b['fix'])+len(b['noindex'])+len(b['robots'])}")
        print(f"    → remove/ignore (junk not indexed): {len(b['junk-not-indexed'])+len(b['remove'])}")
        print(f"    → canonical fixes: {len(b['canonical'])}")
    print(f"  striking-distance queries: {len(opps['striking_distance'])} · low-CTR pages: {len(opps['low_ctr_pages'])}")
    print(f"  content plan items: {len(plan)}")
    print(f"  → gsc-results.json written")


if __name__ == "__main__":
    main()
