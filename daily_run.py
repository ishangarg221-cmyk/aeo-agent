#!/usr/bin/env python3
"""
Daily AEO job — the unattended half of the agent.
==================================================
Runs every day (via cron or GitHub Actions) and does ONLY safe, no-side-effect work:

  AUTO (this script, unattended):
    • run the full pipeline (MYNA auditor + geo audit + geo citations)
    • diff today vs the previous baseline
    • stage DRAFT fixes (llms.txt / schema / robots) into pending-fixes/  — files only
    • write daily-digest.md (scores, deltas, citation status, alerts)
    • exit non-zero if something regressed, so CI flags it

  APPROVE (never done here — needs Ishan's yes):
    • deploying any staged fix to the live site / Shopify
    • any content, price, product, or settings change
  The GitHub Actions workflow turns staged fixes into a Pull Request. Merging the
  PR is the approval. Nothing reaches production without that tap.

Usage:
    python daily_run.py                    # MYNA (myna.config.json)
    python daily_run.py --config x.json    # a client
"""
from __future__ import annotations
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse, datetime as dt, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINES = HERE / "baselines"
STAGING = HERE / "pending-fixes"
DIGEST = HERE / "daily-digest.md"


def sh(cmd: list[str], timeout=240):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        class R:  # minimal shim
            returncode, stdout, stderr = 1, "", str(e)
        return R()


def load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def newest_two(domain: str):
    files = sorted(BASELINES.glob(f"{domain}_*.json"))
    return (load(files[-1]) if files else None,
            load(files[-2]) if len(files) > 1 else None)


def num(d, *ks):
    for k in ks:
        d = d.get(k) if isinstance(d, dict) else None
    return d if isinstance(d, (int, float)) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg_path = a.config or str(HERE / "myna.config.json")
    cfg = load(Path(cfg_path)) or sys.exit(f"Config not found: {cfg_path}")
    url, domain, brand = cfg["url"], cfg["domain"], cfg["brand"]
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    # 1) AUTO — run the full pipeline (saves a fresh baseline)
    print("Running pipeline …")
    sh([sys.executable, str(HERE / "aeo_pipeline.py"), "--config", cfg_path])

    cur, prev = newest_two(domain)
    if not cur:
        sys.exit("Pipeline produced no baseline — check network / config.")

    # 2) AUTO — stage DRAFT fixes into pending-fixes/ (files only, never deployed)
    STAGING.mkdir(exist_ok=True)
    sh(["geo", "fix", "--url", url, "--apply", "--output-dir", str(STAGING)])

    # 3) AUTO — build the digest + alerts
    m_now, m_prev = num(cur, "myna_auditor", "score"), num(prev, "myna_auditor", "score")
    g_now, g_prev = num(cur, "geo_audit", "score"), num(prev, "geo_audit", "score")
    threshold = cfg.get("geo_threshold", 70)

    cites = (cur.get("geo_citations") or {})
    results = cites.get("results") or cites.get("queries") or []
    mentioned = sum(1 for r in results if r.get("mentioned") or r.get("brand_mentioned"))
    cited = sum(1 for r in results if r.get("domain_cited") or r.get("cited"))

    alerts = []
    if isinstance(g_now, (int, float)) and g_now < threshold:
        alerts.append(f"GEO score {g_now} is below threshold {threshold}.")
    if isinstance(g_now, (int, float)) and isinstance(g_prev, (int, float)) and g_now < g_prev:
        alerts.append(f"GEO score dropped {g_prev} → {g_now}.")
    if isinstance(m_now, (int, float)) and isinstance(m_prev, (int, float)) and m_now < m_prev:
        alerts.append(f"MYNA readiness dropped {m_prev} → {m_now}.")
    if results and cited == 0:
        alerts.append(f"{brand}'s domain was cited in 0/{len(results)} AI answers today.")

    def delta(now, was):
        if not isinstance(now, (int, float)) or not isinstance(was, (int, float)):
            return ""
        arrow = "▲" if now > was else "▼" if now < was else "="
        return f" ({arrow}{now - was:+} vs last)"

    lines = [
        f"# Daily AEO digest — {brand} — {today}", "",
        f"- **MYNA readiness:** {m_now if m_now is not None else '—'}/100{delta(m_now, m_prev)}",
        f"- **GEO score:** {g_now if g_now is not None else '—'}/100{delta(g_now, g_prev)}",
        f"- **Citation check:** mentioned {mentioned}/{len(results) or '—'} · domain cited {cited}/{len(results) or '—'}"
        + ("" if results else "  _(no live check — set PERPLEXITY_API_KEY)_"),
        "",
        "## Alerts",
    ]
    lines += [f"- ⚠ {x}" for x in alerts] or ["- none — steady state ✅"]
    staged = sorted(p.name for p in STAGING.rglob("*") if p.is_file())
    lines += ["", "## Pending approval (staged, NOT deployed)"]
    lines += ([f"- `{s}`" for s in staged] or ["- nothing staged today"])
    lines += ["", "_AUTO steps ran unattended. Deploying anything above is an APPROVE"
              " step — review the PR before merging._", ""]
    DIGEST.write_text("\n".join(lines), encoding="utf-8")
    print(DIGEST.read_text())

    # 4) exit code drives CI notification
    sys.exit(1 if alerts else 0)


if __name__ == "__main__":
    main()
