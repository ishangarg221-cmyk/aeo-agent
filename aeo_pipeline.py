#!/usr/bin/env python3
"""
AEO Pipeline — one command, the whole stack.
============================================
Runs, in order, against a target site and merges everything into one
timestamped baseline you can track over time:

  1. MYNA Auditor      (aeo_agent.py)         — MYNA-rules-aware readiness + fixes
  2. geo audit         (geo-optimizer-skill)  — rigorous 47-method GEO score
  3. geo citations     (geo-optimizer-skill)  — REAL proof: is the brand cited? (BYO key)
  4. any extra_tools registered in the config  — governed future GitHub skills

Every run saves baselines/<domain>_<UTC>.json and, if a prior baseline exists,
prints the deltas (score movement + citation movement) so it's a repeatable baseline.

Usage
-----
    python aeo_pipeline.py                       # uses myna.config.json (MYNA)
    python aeo_pipeline.py --config client.json  # reuse for a client site
    python aeo_pipeline.py --url https://x.com --brand "X" --domain x.com --topic "..."
    python aeo_pipeline.py --no-citations        # skip the live check
    python aeo_pipeline.py --no-geo              # skip geo-optimizer, MYNA auditor only

Live citation check needs a key in the environment:
    export PERPLEXITY_API_KEY=...   # recommended — returns real cited source URLs
"""
from __future__ import annotations
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse, datetime as dt, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINES = HERE / "baselines"
BASELINES.mkdir(exist_ok=True)


def load_config(path: str | None) -> dict:
    p = Path(path) if path else HERE / "myna.config.json"
    if not p.exists():
        sys.exit(f"Config not found: {p}")
    return json.loads(p.read_text())


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def run_json(cmd: list[str]) -> dict | None:
    """Run a command expected to emit JSON on stdout; tolerate noise."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except Exception as e:
        return {"_error": str(e)}
    out = r.stdout.strip()
    # grab the JSON object even if the tool prints a banner first
    start = out.find("{")
    if start != -1:
        try:
            return json.loads(out[start:])
        except Exception:
            pass
    return {"_raw": out[-2000:], "_stderr": r.stderr[-800:], "_code": r.returncode}


# ------------------------------------------------------------------ steps
def step_myna_auditor(url: str, brand: str, topic: str) -> dict:
    print("\n[1/4] MYNA Auditor (aeo_agent.py) …")
    try:
        sys.path.insert(0, str(HERE))
        import aeo_agent  # local
        rep = aeo_agent.run(url, brand=brand, category=topic, live=False)
        print(f"      MYNA readiness score: {rep['score']}/100 — {rep['grade']}")
        return rep
    except SystemExit as e:
        print(f"      ! auditor could not reach {url}: {e}")
        return {"_error": str(e)}
    except Exception as e:
        print(f"      ! auditor error: {e}")
        return {"_error": str(e)}


def step_geo_audit(url: str, threshold: int) -> dict | None:
    print("\n[2/4] geo audit (geo-optimizer-skill) …")
    if not have("geo"):
        print("      ! 'geo' not installed. Run: pip install geo-optimizer-skill")
        return None
    data = run_json(["geo", "audit", "--url", url, "--format", "json"])
    score = (data or {}).get("score")
    if score is not None:
        band = data.get("band", "")
        flag = "  ⚠ BELOW THRESHOLD" if isinstance(score, (int, float)) and score < threshold else ""
        print(f"      GEO score: {score}/100  ({band}){flag}")
    else:
        print("      ! no score returned (see saved JSON for raw output)")
    return data


def step_geo_citations(brand: str, domain: str, topic: str, queries: list[str]) -> dict | None:
    print("\n[3/4] geo citations — real AI citation check …")
    if not have("geo"):
        print("      ! 'geo' not installed; skipping.")
        return None
    key_set = any(os.getenv(k) for k in
                  ("PERPLEXITY_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY"))
    if not key_set:
        print("      ! No API key set. export PERPLEXITY_API_KEY to enable the live check.")
        return {"_skipped": "no_api_key"}
    cmd = ["geo", "citations", "--brand", brand, "--domain", domain, "--topic", topic, "--format", "json"]
    for q in queries:
        cmd += ["--query", q]
    data = run_json(cmd)
    _summarize_citations(data)
    return data


def _summarize_citations(data: dict | None):
    if not data or "_error" in (data or {}) or "_skipped" in (data or {}):
        return
    results = data.get("results") or data.get("queries") or []
    mentioned = sum(1 for r in results if r.get("mentioned") or r.get("brand_mentioned"))
    cited = sum(1 for r in results if r.get("domain_cited") or r.get("cited"))
    total = len(results) if results else "?"
    print(f"      brand mentioned in {mentioned}/{total} answers · domain cited in {cited}/{total}")


def step_extra_tools(cfg: dict, ctx: dict) -> dict:
    tools = [t for t in cfg.get("extra_tools", []) if t.get("enabled")]
    print(f"\n[4/4] extra registered skills: {len(tools)} enabled")
    out = {}
    for t in tools:
        name = t.get("name", "unnamed")
        cmd = [c.format(**ctx) for c in t.get("cmd", [])]
        exe = cmd[0] if cmd else ""
        if not have(exe):
            print(f"      ! {name}: '{exe}' not installed; skipping.")
            out[name] = {"_error": f"{exe} not found"}
            continue
        print(f"      running {name}: {' '.join(cmd)}")
        out[name] = run_json(cmd)
    return out


# --------------------------------------------------------------- baseline
def prior_baseline(domain: str) -> dict | None:
    files = sorted(BASELINES.glob(f"{domain}_*.json"))
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text())
    except Exception:
        return None


def show_deltas(prev: dict, cur: dict):
    print("\n" + "─" * 56)
    print("  DELTAS vs last baseline")
    print("─" * 56)
    def g(d, *ks):
        for k in ks:
            d = (d or {}).get(k) if isinstance(d, dict) else None
        return d
    pairs = [
        ("MYNA readiness", g(prev, "myna_auditor", "score"), g(cur, "myna_auditor", "score")),
        ("GEO score",      g(prev, "geo_audit", "score"),    g(cur, "geo_audit", "score")),
    ]
    for label, a, b in pairs:
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            arrow = "▲" if b > a else "▼" if b < a else "="
            print(f"  {label:<18} {a} → {b}  {arrow} {b - a:+}")
        else:
            print(f"  {label:<18} (no comparable value)")


# -------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="AEO Pipeline — full stack, one command")
    ap.add_argument("--config")
    ap.add_argument("--url"); ap.add_argument("--brand")
    ap.add_argument("--domain"); ap.add_argument("--topic")
    ap.add_argument("--no-citations", action="store_true")
    ap.add_argument("--no-geo", action="store_true")
    a = ap.parse_args()

    cfg = load_config(a.config)
    url = a.url or cfg["url"]
    brand = a.brand or cfg["brand"]
    domain = a.domain or cfg["domain"]
    topic = a.topic or cfg.get("topic", brand)
    queries = cfg.get("citation_queries", [])
    threshold = cfg.get("geo_threshold", 70)
    ctx = {"url": url, "brand": brand, "domain": domain, "topic": topic}

    print("═" * 56)
    print(f"  AEO PIPELINE · {brand} · {url}")
    print(f"  {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}")
    print("═" * 56)

    report = {"meta": {"brand": brand, "domain": domain, "url": url,
                       "utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}}
    report["myna_auditor"] = step_myna_auditor(url, brand, topic)
    report["geo_audit"] = None if a.no_geo else step_geo_audit(url, threshold)
    report["geo_citations"] = None if (a.no_geo or a.no_citations) \
        else step_geo_citations(brand, domain, topic, queries)
    report["extra_tools"] = step_extra_tools(cfg, ctx)

    prev = prior_baseline(domain)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = BASELINES / f"{domain}_{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    if prev:
        show_deltas(prev, report)
    print("\n" + "═" * 56)
    print(f"  Baseline saved → {out_path.relative_to(HERE)}")
    print("  Re-run in 2–4 weeks and compare the deltas.")
    print("═" * 56 + "\n")


if __name__ == "__main__":
    main()
