#!/usr/bin/env python3
"""
build_dashboard.py — turns an audit into a self-contained visual dashboard.
==========================================================================
Runs the auditor, reframes every finding as a Doubt-Engineer entry (the doubt,
the thinker who flags it, the exact subtraction), pulls score history from
baselines/ for the trend, and writes ONE self-contained file:

    dashboard/index.html   (open by double-click, or host on GitHub Pages / Vercel)

No server, no fetch, no external data — the data is baked into the HTML, so it
opens anywhere. The GitHub Action regenerates it daily so the hosted page is
always current and you never touch a terminal.

Usage:
    python build_dashboard.py                 # MYNA (myna.config.json)
    python build_dashboard.py --config x.json
"""
from __future__ import annotations
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8"); _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse, datetime as dt, html, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINES = HERE / "baselines"
OUT = HERE / "dashboard"
OUT.mkdir(exist_ok=True)


def load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# --- Doubt-Engineer lens: map an audit fix to a doubt + thinker + subtraction ---
def doubt_for(sev: str, text: str, brand: str) -> dict:
    t = text.lower()
    if any(k in t for k in ("robots", "crawl", "bot", "unblock")):
        return {"doubt": "Am I even allowed to read this site?",
                "voice": "the AI crawler", "thinker": "Taleb",
                "principle": "One line in a config file can make you invisible to every AI engine at once. That is pure fragility — remove it first."}
    if "llms.txt" in t:
        return {"doubt": "Which of this site's pages actually matter?",
                "voice": "the AI engine", "thinker": "Sharp",
                "principle": "Mental availability: make the brand effortless to find and recall. An llms.txt is your shortcut into the model's shortlist."}
    if any(k in t for k in ("schema", "json-ld", "organization", "product", "faqpage", "breadcrumb")):
        return {"doubt": f"Is {brand} a real, verifiable entity — or just a page?",
                "voice": "the AI engine", "thinker": "Ogilvy",
                "principle": "Facts, structured, are what a serious brand supplies. Schema is your evidence file — it turns claims into citable data."}
    if any(k in t for k in ("question", "answer", "heading", "h1", "h2", "table", "list")):
        return {"doubt": "Does gold plating tarnish? Is zinc alloy cheap? Is this a real brand?",
                "voice": "your buyer", "thinker": "Kahneman",
                "principle": "Buyers ask in questions. If your page doesn't answer the exact question the way they ask it, the engine quotes whoever does. Own the doubt, own the citation."}
    if any(k in t for k in ("word", "render", "extractab", "javascript", "text-to-code")):
        return {"doubt": "Is there real substance here, or an empty JS shell?",
                "voice": "the AI crawler", "thinker": "Christensen",
                "principle": "The content must do its job in raw HTML. Hide it behind JavaScript and the crawler hires a competitor instead."}
    return {"doubt": f"Is this the same {brand} everywhere, or am I guessing?",
            "voice": "the AI engine", "thinker": "Porter",
            "principle": "Consistent positioning across every surface is the moat. Title, meta, canonical and sameAs are how the engine confirms one coherent brand."}


def build_data(cfg: dict) -> dict:
    sys_path = str(HERE)
    if sys_path not in _sys.path:
        _sys.path.insert(0, sys_path)
    import aeo_agent
    url, brand, domain = cfg["url"], cfg["brand"], cfg["domain"]

    try:
        rep = aeo_agent.run(url, brand=brand, category=cfg.get("topic", ""), live=False)
    except SystemExit:
        rep = {"score": None, "grade": "could not reach site", "sections": {}, "ranked_fixes": []}

    # geo score + citations from latest baseline, if the pipeline has run
    geo_score = cited = total_q = None
    files = sorted(BASELINES.glob(f"{domain}_*.json"))
    latest = load(files[-1]) if files else None
    if latest:
        g = ((latest.get("geo_audit") or {}) or {}).get("score")
        geo_score = g if isinstance(g, (int, float)) else None
        c = latest.get("geo_citations") or {}
        res = c.get("results") or c.get("queries") or []
        if res:
            total_q = len(res)
            cited = sum(1 for r in res if r.get("domain_cited") or r.get("cited"))

    # history trend
    history = []
    for f in files[-14:]:
        d = load(f) or {}
        history.append({
            "date": d.get("meta", {}).get("utc", f.stem.split("_")[-1])[:10],
            "myna": ((d.get("myna_auditor") or {}) or {}).get("score"),
            "geo": ((d.get("geo_audit") or {}) or {}).get("score"),
        })

    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    ledger = []
    for sev, text in sorted(rep.get("ranked_fixes", []), key=lambda x: order.get(x[0], 9)):
        d = doubt_for(sev, text, brand)
        ledger.append({"severity": sev, "subtract": text, **d})

    # already-good signals (resolved doubts)
    resolved = []
    for name, s in (rep.get("sections") or {}).items():
        for f in s.get("findings", []):
            if any(k in f.lower() for k in ("present", "allowed", "good", "detected", "✓")):
                resolved.append(f.replace("✓", "").strip())

    # staged fix files
    staged = []
    pf = HERE / "pending-fixes"
    if pf.exists():
        staged = sorted(p.name for p in pf.rglob("*") if p.is_file())

    # today's content draft
    from connectors import content as content_mod
    cdraft = content_mod.todays_draft(HERE / "content.config.json")

    return {
        "brand": brand, "url": url, "domain": domain,
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
        "readiness": rep.get("score"), "grade": rep.get("grade"),
        "geo": geo_score, "cited": cited, "total_q": total_q,
        "ledger": ledger, "resolved": resolved[:8], "staged": staged,
        "history": history, "content": cdraft,
    }


# ------------------------------------------------------------------ render
SEV_COLOR = {"CRITICAL": "#e5544b", "HIGH": "#e0913a", "MEDIUM": "#b9a15a", "LOW": "#6f7d78"}


def esc(x):
    return html.escape(str(x if x is not None else ""))


def ring(value, label, sub=""):
    if not isinstance(value, (int, float)):
        pct, disp = 0, "—"
    else:
        pct, disp = value, str(int(value))
    circ = 2 * 3.14159 * 52
    off = circ * (1 - pct / 100)
    return f"""
    <div class="ring">
      <svg viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="52" class="ring-bg"/>
        <circle cx="60" cy="60" r="52" class="ring-fg"
                style="stroke-dasharray:{circ:.1f};stroke-dashoffset:{off:.1f}"/>
      </svg>
      <div class="ring-num">{disp}<span>{'/100' if disp!='—' else ''}</span></div>
      <div class="ring-label">{esc(label)}</div>
      <div class="ring-sub">{esc(sub)}</div>
    </div>"""


def sparkline(history):
    pts = [(h["date"], h["myna"]) for h in history if isinstance(h.get("myna"), (int, float))]
    if len(pts) < 2:
        return '<div class="spark-empty">Trend appears after a few daily runs.</div>'
    w, h = 520, 90
    xs = [i / (len(pts) - 1) * (w - 10) + 5 for i in range(len(pts))]
    ys = [h - (v / 100) * (h - 20) - 10 for _, v in pts]
    path = " ".join(f"{'M' if i==0 else 'L'}{xs[i]:.1f},{ys[i]:.1f}" for i in range(len(pts)))
    dots = "".join(f'<circle cx="{xs[i]:.1f}" cy="{ys[i]:.1f}" r="3"/>' for i in range(len(pts)))
    return f'<svg class="spark" viewBox="0 0 {w} {h}"><path d="{path}"/>{dots}</svg>'


def render(data: dict) -> str:
    b = esc(data["brand"])
    cite_txt = (f'{data["cited"]}/{data["total_q"]} answers'
                if data.get("total_q") else "no key yet")
    ledger_html = ""
    for i, e in enumerate(data["ledger"]):
        col = SEV_COLOR.get(e["severity"], "#6f7d78")
        ledger_html += f"""
        <div class="doubt">
          <button class="doubt-head" onclick="this.parentElement.classList.toggle('open')">
            <span class="sev" style="--c:{col}">{esc(e['severity'])}</span>
            <span class="doubt-q">“{esc(e['doubt'])}”</span>
            <span class="chev">▾</span>
          </button>
          <div class="doubt-body">
            <div class="row"><span class="k">Whose doubt</span><span class="v">{esc(e['voice'])}</span></div>
            <div class="row"><span class="k">Lens</span><span class="v">{esc(e['thinker'])} — {esc(e['principle'])}</span></div>
            <div class="row subtract"><span class="k">Subtract it</span><span class="v">{esc(e['subtract'])}</span></div>
          </div>
        </div>"""
    if not data["ledger"]:
        ledger_html = '<div class="empty">No active doubts — this page is citation-ready. Rare. Verify with a live citation check.</div>'

    resolved_html = "".join(f"<li>{esc(r)}</li>" for r in data["resolved"]) or "<li>—</li>"
    staged_html = "".join(f"<code>{esc(s)}</code>" for s in data["staged"]) or "<span class='muted'>none staged</span>"

    c = data["content"]
    if c.get("post_day") and c.get("rendered"):
        content_html = f"<pre class='draft'>{esc(c['rendered'])}</pre>"
    elif c.get("post_day"):
        content_html = "<div class='muted'>Post day — queue is empty. Add posts to content.config.json.</div>"
    else:
        content_html = f"<div class='muted'>No post scheduled today. Next: {esc(c.get('next','—'))}.</div>"

    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{b} — Doubt Ledger</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,500&family=Jost:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root{{--bg:#0a0a0a;--ink:#f5f1ea;--line:rgba(245,241,234,.12);--glass:rgba(245,241,234,.035);--muted:rgba(245,241,234,.55)}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--ink);font-family:'Jost',sans-serif;font-weight:300;line-height:1.6;
       background-image:radial-gradient(1200px 600px at 70% -10%,rgba(245,241,234,.05),transparent)}}
  .wrap{{max-width:960px;margin:0 auto;padding:48px 24px 96px}}
  h1,h2,h3{{font-family:'Cormorant Garamond',serif;font-weight:400;letter-spacing:.01em;margin:0}}
  h1{{font-size:44px;line-height:1.05}}
  h1 em{{font-style:italic;font-weight:500}}
  .eyebrow{{font-family:'Jost';font-size:11px;letter-spacing:.28em;text-transform:uppercase;color:var(--muted)}}
  .rule{{height:1px;background:var(--line);margin:14px 0 0}}
  header .meta{{color:var(--muted);font-size:13px;margin-top:10px}}
  .rings{{display:flex;gap:18px;flex-wrap:wrap;margin:36px 0 8px}}
  .ring{{flex:1;min-width:150px;background:var(--glass);border:1px solid var(--line);border-radius:18px;
        padding:22px 18px;text-align:center;backdrop-filter:blur(8px);position:relative}}
  .ring svg{{width:112px;height:112px;transform:rotate(-90deg)}}
  .ring-bg{{fill:none;stroke:var(--line);stroke-width:8}}
  .ring-fg{{fill:none;stroke:var(--ink);stroke-width:8;stroke-linecap:round;transition:stroke-dashoffset 1s ease}}
  .ring-num{{font-family:'Cormorant Garamond';font-size:34px;margin-top:-74px;margin-bottom:34px}}
  .ring-num span{{font-size:15px;color:var(--muted)}}
  .ring-label{{font-size:12px;letter-spacing:.2em;text-transform:uppercase}}
  .ring-sub{{font-size:12px;color:var(--muted);margin-top:2px}}
  section{{margin-top:44px}}
  .spark{{width:100%;height:90px;margin-top:16px}}
  .spark path{{fill:none;stroke:var(--ink);stroke-width:1.5;opacity:.8}}
  .spark circle{{fill:var(--ink)}}
  .spark-empty{{color:var(--muted);font-size:14px;margin-top:12px}}
  .doubt{{border:1px solid var(--line);border-radius:14px;margin:12px 0;background:var(--glass);overflow:hidden}}
  .doubt-head{{width:100%;text-align:left;background:none;border:0;color:var(--ink);cursor:pointer;
              display:flex;align-items:center;gap:14px;padding:16px 18px;font-family:'Jost';font-size:16px}}
  .sev{{font-size:10px;letter-spacing:.16em;padding:4px 9px;border-radius:99px;border:1px solid var(--c);color:var(--c);white-space:nowrap}}
  .doubt-q{{font-family:'Cormorant Garamond';font-style:italic;font-size:20px;flex:1}}
  .chev{{color:var(--muted);transition:transform .25s}}
  .doubt.open .chev{{transform:rotate(180deg)}}
  .doubt-body{{max-height:0;overflow:hidden;transition:max-height .3s ease;padding:0 18px}}
  .doubt.open .doubt-body{{max-height:420px;padding-bottom:18px}}
  .row{{display:flex;gap:16px;padding:9px 0;border-top:1px solid var(--line)}}
  .row .k{{flex:0 0 108px;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);padding-top:3px}}
  .row .v{{flex:1;font-size:15px}}
  .row.subtract .v{{color:var(--ink)}}
  .row.subtract{{background:rgba(245,241,234,.04);margin:6px -18px 0;padding:12px 18px;border-radius:0 0 12px 12px}}
  ul.good{{list-style:none;padding:0;columns:2;gap:24px}}
  ul.good li{{font-size:14px;color:var(--muted);padding:5px 0}}
  ul.good li::before{{content:'— ';color:var(--ink)}}
  .staged code{{display:inline-block;font-family:ui-monospace,monospace;font-size:12px;background:var(--glass);
               border:1px solid var(--line);border-radius:8px;padding:6px 10px;margin:4px 6px 0 0}}
  pre.draft{{white-space:pre-wrap;font-family:'Jost';font-weight:300;font-size:14px;background:var(--glass);
            border:1px solid var(--line);border-radius:14px;padding:20px;color:var(--ink)}}
  .muted{{color:var(--muted);font-size:14px}}
  .empty{{color:var(--muted);padding:18px;border:1px dashed var(--line);border-radius:14px}}
  footer{{margin-top:64px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:18px}}
  @media(max-width:640px){{h1{{font-size:34px}}ul.good{{columns:1}}.doubt-q{{font-size:17px}}}}
</style></head><body><div class="wrap">
  <header>
    <div class="eyebrow">Doubt Ledger · AI-citation audit</div>
    <div class="rule"></div>
    <h1 style="margin-top:18px">{b} &amp; the <em>disbelief</em> between you and your next citation</h1>
    <div class="meta">{esc(data['url'])} · generated {esc(data['generated'])} · runs daily</div>
  </header>

  <div class="rings">
    {ring(data['readiness'], 'Readiness', data.get('grade',''))}
    {ring(data['geo'], 'GEO score', 'rigorous 47-method' if data.get('geo') is not None else 'run pipeline')}
    {ring((data['cited']/data['total_q']*100) if data.get('total_q') else None, 'Cited by AI', cite_txt)}
  </div>

  <section>
    <div class="eyebrow">Trend</div><div class="rule"></div>
    {sparkline(data['history'])}
  </section>

  <section>
    <div class="eyebrow">Active doubts — work top to bottom</div><div class="rule"></div>
    <p class="muted" style="margin-top:14px">Each is a disbelief a crawler, an engine, or a buyer holds right now. Growth is the subtraction of disbelief — so this list, in order, is your work.</p>
    {ledger_html}
  </section>

  <section>
    <div class="eyebrow">Already subtracted</div><div class="rule"></div>
    <ul class="good">{resolved_html}</ul>
  </section>

  <section>
    <div class="eyebrow">Ready-to-paste fixes (staged, not deployed)</div><div class="rule"></div>
    <p class="staged" style="margin-top:14px">{staged_html}</p>
    <p class="muted">Files live in <code>pending-fixes/</code>. Review, then paste into your theme — deploying is your call.</p>
  </section>

  <section>
    <div class="eyebrow">Today's post — draft only</div><div class="rule"></div>
    {content_html}
  </section>

  <footer>Nothing here was published, deployed, or changed. This page is a read-only view of the daily audit.</footer>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg = load(Path(a.config or (HERE / "myna.config.json"))) or _sys.exit("config not found")
    data = build_data(cfg)
    out = OUT / "index.html"
    out.write_text(render(data), encoding="utf-8")
    print(f"Dashboard written → {out}")
    print("Open it: double-click the file, or host dashboard/ on GitHub Pages / Vercel.")


if __name__ == "__main__":
    main()
