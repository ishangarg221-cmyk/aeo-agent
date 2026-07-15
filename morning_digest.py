#!/usr/bin/env python3
"""
Morning digest — one 9am report across the whole business. DRAFTS ONLY.
=======================================================================
Consolidates three fronts into a single Markdown digest you skim over chai:

  • AEO/SEO   — today's scores, deltas, alerts, staged fixes   (from daily_run.py)
  • Shopify   — yesterday's sales, low stock, thin-content PDPs (read-only)
  • Content   — today's M/W/F post draft (copy-paste-ready)     (never posted)

Nothing here changes your store, your site, or your LinkedIn. Every actionable
item is a draft or an alert. Deploying/publishing is always your call.

Delivery: writes digest/<date>.md and prints it. If SMTP_* env vars are set it
also emails the digest; otherwise it's picked up as a CI artifact.

Usage:
    python morning_digest.py                 # MYNA
    python morning_digest.py --config x.json
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
sys.path.insert(0, str(HERE))
from connectors.shopify import ShopifyReadOnly
from connectors import content as content_mod

BASELINES = HERE / "baselines"
DIGEST_DIR = HERE / "digest"
DIGEST_DIR.mkdir(exist_ok=True)


def load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def num(d, *ks):
    for k in ks:
        d = d.get(k) if isinstance(d, dict) else None
    return d if isinstance(d, (int, float)) else None


# ---------------------------------------------------------------- sections
def aeo_section(cfg_path: str, domain: str) -> tuple[list[str], list[str]]:
    # run the AEO daily job (writes a fresh baseline + stages fixes); ignore its exit code
    subprocess.run([sys.executable, str(HERE / "daily_run.py"), "--config", cfg_path],
                   capture_output=True, text=True)
    files = sorted(BASELINES.glob(f"{domain}_*.json"))
    cur = load(files[-1]) if files else None
    prev = load(files[-2]) if len(files) > 1 else None
    m, mp = num(cur, "myna_auditor", "score"), num(prev, "myna_auditor", "score")
    g, gp = num(cur, "geo_audit", "score"), num(prev, "geo_audit", "score")

    def d(now, was):
        if not isinstance(now, (int, float)) or not isinstance(was, (int, float)):
            return ""
        a = "▲" if now > was else "▼" if now < was else "="
        return f" ({a}{now - was:+})"

    lines = ["## 1. AEO / SEO",
             f"- MYNA readiness: **{m if m is not None else '—'}/100**{d(m, mp)}",
             f"- GEO score: **{g if g is not None else '—'}/100**{d(g, gp)}"]
    cites = (cur or {}).get("geo_citations") or {}
    res = cites.get("results") or cites.get("queries") or []
    if res:
        cited = sum(1 for r in res if r.get("domain_cited") or r.get("cited"))
        lines.append(f"- AI citation: domain cited in **{cited}/{len(res)}** answers")
    else:
        lines.append("- AI citation: _no live check (set PERPLEXITY_API_KEY)_")
    staged = sorted(p.name for p in (HERE / "pending-fixes").rglob("*") if p.is_file()) \
        if (HERE / "pending-fixes").exists() else []
    if staged:
        lines.append(f"- Staged fixes awaiting approval: {', '.join(f'`{s}`' for s in staged)}")

    alerts = []
    if isinstance(g, (int, float)) and isinstance(gp, (int, float)) and g < gp:
        alerts.append(f"GEO score dropped {gp} → {g}")
    if res and all(not (r.get("domain_cited") or r.get("cited")) for r in res):
        alerts.append("MYNA not cited in any AI answer today")
    return lines, alerts


def shopify_section() -> tuple[list[str], list[str]]:
    shop = ShopifyReadOnly()
    if not shop.configured:
        return (["## 2. Shopify",
                 "- _not connected. Set SHOPIFY_STORE + SHOPIFY_ADMIN_TOKEN "
                 "(read_orders, read_products) to light this up._"], [])
    lines, alerts = ["## 2. Shopify"], []
    s = shop.sales_yesterday()
    if "_error" in s:
        lines.append(f"- sales: _error — {s['_error']}_")
    else:
        lines.append(f"- Yesterday: **{s['orders']} orders · {s['currency']} "
                     f"{s['revenue']:,} · {s['units']} units**")
    low = shop.low_stock()
    if low and "_error" not in low[0]:
        lines.append(f"- Low stock ({len(low)}): "
                     + ", ".join(f"{x['product']} ({x['qty']})" for x in low[:8]))
        if low:
            alerts.append(f"{len(low)} variant(s) at/near out-of-stock")
    thin = shop.products_missing_schema_fields()
    if thin and "_error" not in thin[0]:
        lines.append(f"- **Draft AEO fix:** {len(thin)} active PDP(s) have thin "
                     f"descriptions (weak Product schema). Top: "
                     + ", ".join(x["title"] for x in thin[:5]))
    return lines, alerts


def content_section(today: dt.date) -> tuple[list[str], list[str]]:
    res = content_mod.todays_draft(HERE / "content.config.json", today)
    lines = ["## 3. Content (draft only — do not auto-post)"]
    if not res.get("post_day"):
        lines.append(f"- No post scheduled today. Next: **{res.get('next', '—')}**.")
        return lines, []
    if res.get("empty"):
        lines.append("- Post day, but the queue is empty — add posts to `content.config.json`.")
        return lines, ["content queue empty on a post day"]
    lines += ["- **Today's post is drafted below — review, then publish manually.**", "",
              "```", res["rendered"], "```"]
    return lines, []


# -------------------------------------------------------------------- email
def maybe_email(subject: str, body_md: str):
    import os
    host, user, pw = os.getenv("SMTP_HOST"), os.getenv("SMTP_USER"), os.getenv("SMTP_PASS")
    to = os.getenv("DIGEST_TO")
    if not all([host, user, pw, to]):
        return "not configured"
    import smtplib, ssl
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.set_content(body_md)
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587"))) as srv:
            srv.starttls(context=ssl.create_default_context())
            srv.login(user, pw)
            srv.send_message(msg)
        return "sent"
    except Exception as e:
        return f"error: {e}"


# -------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg_path = a.config or str(HERE / "myna.config.json")
    cfg = load(Path(cfg_path)) or sys.exit(f"Config not found: {cfg_path}")
    brand, domain = cfg["brand"], cfg["domain"]
    today = dt.datetime.now(dt.timezone.utc).date()

    all_alerts = []
    body = [f"# {brand} — morning digest — {today:%A %d %b %Y}", ""]
    for section_fn in (lambda: aeo_section(cfg_path, domain),
                       shopify_section,
                       lambda: content_section(today)):
        lines, alerts = section_fn()
        body += lines + [""]
        all_alerts += alerts

    header = ["## ⚠ Needs your eyes"] + ([f"- {x}" for x in all_alerts]
                                          or ["- nothing urgent — steady state ✅"]) + [""]
    body = body[:2] + header + body[2:]
    body += ["---", "_All items are drafts or alerts. Nothing was published, deployed,"
             " or changed. Approvals are yours._"]
    text = "\n".join(body)

    out = DIGEST_DIR / f"{today:%Y-%m-%d}.md"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n[digest saved → {out.relative_to(HERE)} · email: {maybe_email(f'{brand} digest {today}', text)}]")


if __name__ == "__main__":
    main()
