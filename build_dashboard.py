#!/usr/bin/env python3
"""build_dashboard.py — self-contained visual dashboard (site-wide, from crawl-results.json)."""
from __future__ import annotations
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8"); _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse, datetime as dt, html, json
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
BASELINES = HERE / "baselines"
OUT = HERE / "dashboard"; OUT.mkdir(exist_ok=True)
SEV_COLOR = {"CRITICAL": "#e5544b", "HIGH": "#e0913a", "MEDIUM": "#b9a15a", "LOW": "#6f7d78"}


def load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def esc(x):
    return html.escape(str(x if x is not None else ""))


def doubt_for(sev, text, brand):
    t = text.lower()
    if any(k in t for k in ("robots", "crawl", "bot", "unblock")):
        return {"doubt": "Am I even allowed to read this site?", "voice": "the AI crawler", "thinker": "Taleb", "principle": "One config line can make you invisible to every AI engine at once. Pure fragility — remove it first."}
    if "llms.txt" in t:
        return {"doubt": "Which of this site's pages actually matter?", "voice": "the AI engine", "thinker": "Sharp", "principle": "Mental availability: make the brand effortless to find and recall. llms.txt is your shortcut into the model's shortlist."}
    if any(k in t for k in ("schema", "json-ld", "organization", "product", "faqpage", "breadcrumb")):
        return {"doubt": f"Is {brand} a real, verifiable entity — or just a page?", "voice": "the AI engine", "thinker": "Ogilvy", "principle": "Facts, structured, are what a serious brand supplies. Schema turns claims into citable data."}
    if any(k in t for k in ("question", "answer", "heading", "h1", "h2", "table", "list")):
        return {"doubt": "Does gold plating tarnish? Is zinc alloy cheap? Is this a real brand?", "voice": "your buyer", "thinker": "Kahneman", "principle": "Buyers ask in questions. Answer the exact question the way they ask it, or the engine quotes whoever does."}
    if any(k in t for k in ("word", "render", "extractab", "javascript", "text-to-code")):
        return {"doubt": "Is there real substance here, or an empty JS shell?", "voice": "the AI crawler", "thinker": "Christensen", "principle": "Content must do its job in raw HTML. Hide it behind JavaScript and the crawler hires a competitor."}
    return {"doubt": f"Is this the same {brand} everywhere, or am I guessing?", "voice": "the AI engine", "thinker": "Porter", "principle": "Consistent positioning across every surface is the moat. Title, meta, canonical and sameAs confirm one coherent brand."}


def ring(value, label, sub=""):
    if not isinstance(value, (int, float)):
        pct, disp = 0, "—"
    else:
        pct, disp = value, str(int(value))
    circ = 2 * 3.14159 * 52; off = circ * (1 - pct / 100)
    return f'<div class="ring"><svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="52" class="ring-bg"/><circle cx="60" cy="60" r="52" class="ring-fg" style="stroke-dasharray:{circ:.1f};stroke-dashoffset:{off:.1f}"/></svg><div class="ring-num">{disp}<span>{"/100" if disp!="—" else ""}</span></div><div class="ring-label">{esc(label)}</div><div class="ring-sub">{esc(sub)}</div></div>'


def geo_cite(domain):
    files = sorted(BASELINES.glob(f"{domain}_*.json")); latest = load(files[-1]) if files else None
    geo = cited = total = None
    if latest:
        g = ((latest.get("geo_audit") or {}) or {}).get("score"); geo = g if isinstance(g, (int, float)) else None
        res = (latest.get("geo_citations") or {}).get("results") or (latest.get("geo_citations") or {}).get("queries") or []
        if res:
            total = len(res); cited = sum(1 for r in res if r.get("domain_cited") or r.get("cited"))
    return geo, cited, total


def dcard(sev, text, brand):
    d = doubt_for(sev, text, brand); col = SEV_COLOR.get(sev, "#6f7d78")
    return f'<div class="doubt"><button class="doubt-head" onclick="this.parentElement.classList.toggle(\'open\')"><span class="sev" style="--c:{col}">{esc(sev)}</span><span class="doubt-q">\u201c{esc(d["doubt"])}\u201d</span><span class="chev">\u25be</span></button><div class="doubt-body"><div class="row"><span class="k">Whose doubt</span><span class="v">{esc(d["voice"])}</span></div><div class="row"><span class="k">Lens</span><span class="v">{esc(d["thinker"])} \u2014 {esc(d["principle"])}</span></div><div class="row subtract"><span class="k">Subtract it</span><span class="v">{esc(text)}</span></div></div></div>'


def render_gsc(g):
    if not g:
        return ""
    parts = ['<section><div class="eyebrow">Search Console — real Google data</div><div class="rule"></div>']
    parts.append(f'<p class="muted" style="margin-top:12px">{g["totals"].get("clicks",0)} clicks · {g["totals"].get("impressions",0)} impressions (28d) · {esc(g.get("mode"))} mode</p>')
    diag = g.get("index")
    if diag:
        b = diag["buckets"]
        push = len(b.get("fix", [])) + len(b.get("noindex", [])) + len(b.get("robots", []))
        junk = len(b.get("junk-not-indexed", [])) + len(b.get("remove", []))
        parts.append('<div class="idx"><div class="idxc"><b>'+str(len(b.get("indexed",[])))+'</b><span>indexed</span></div>'
                     f'<div class="idxc push"><b>{push}</b><span>valuable · push these</span></div>'
                     f'<div class="idxc junk"><b>{junk}</b><span>junk · noindex/remove</span></div>'
                     f'<div class="idxc"><b>{len(b.get("canonical",[]))}</b><span>canonical fix</span></div></div>')
        pushlist = (b.get("fix", []) + b.get("noindex", []) + b.get("robots", []))[:10]
        if pushlist:
            parts.append('<p class="eyebrow" style="margin-top:22px">Push into the index — valuable pages Google is skipping</p>')
            for it in pushlist:
                parts.append(f'<div class="issue"><span class="issue-t">{esc(urlparse(it["url"]).path)}</span><span class="issue-n">{esc(it.get("state",""))}</span></div><div class="muted" style="margin:-4px 0 10px">{esc(it.get("advice",""))}</div>')
        rmlist = (b.get("junk-not-indexed", []) + b.get("remove", []))[:8]
        if rmlist:
            parts.append('<p class="eyebrow" style="margin-top:18px">Safe to leave unindexed / noindex — junk &amp; duplicates</p>')
            for it in rmlist:
                parts.append(f'<div class="issue"><span class="issue-t">{esc(urlparse(it["url"]).path)}</span><span class="issue-n">{esc(it.get("state",""))}</span></div>')
    opp = g.get("opportunities", {})
    sd = opp.get("striking_distance", [])
    if sd:
        parts.append('<p class="eyebrow" style="margin-top:22px">Striking distance — one push from page one</p>')
        for q in sd[:10]:
            parts.append(f'<div class="issue"><span class="issue-t">{esc(q["query"])}</span><span class="issue-n">#{q["position"]} · {q["impressions"]} impr</span></div>')
    plan = g.get("content_plan", [])
    if plan:
        parts.append('<p class="eyebrow" style="margin-top:22px">Content plan — build these next</p>')
        for it in plan[:10]:
            parts.append(f'<div class="issue"><span class="issue-t">{esc(it["target"])}</span><span class="issue-n">{esc(it["why"])}</span></div><div class="muted" style="margin:-4px 0 10px">{esc(it["action"])}</div>')
    sm = g.get("sitemaps", [])
    if sm:
        parts.append('<p class="eyebrow" style="margin-top:18px">Sitemap</p>')
        for s in sm:
            parts.append(f'<div class="muted">{esc(s.get("path",""))} — {esc(s.get("note",""))}</div>')
    parts.append("</section>")
    return "".join(parts)


def render_site(cr, content):
    brand = esc(cr["brand"]); geo, cited, total = geo_cite(cr["domain"])
    gsc = load(HERE / "gsc-results.json")
    cite_txt = f"{cited}/{total} answers" if total else "no key yet"
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    dom = [(s, x) for sec in cr.get("domain_sections", {}).values() for (s, x) in sec.get("fixes", [])]
    dom.sort(key=lambda x: order.get(x[0], 9))
    band = "".join(dcard(s, x, brand) for s, x in dom) or '<div class="empty">No sitewide blockers \u2014 crawlability and llms.txt are in good shape.</div>'
    rows = ""
    for it in cr.get("sitewide_issues", []):
        col = SEV_COLOR.get(it["sev"], "#6f7d78")
        rows += f'<div class="issue"><span class="sev" style="--c:{col}">{esc(it["sev"])}</span><span class="issue-t">{esc(it["issue"])}</span><span class="issue-n">{it["count"]} pages</span></div>'
    rows = rows or '<div class="empty">No repeated page issues found.</div>'
    scored = sorted([p for p in cr.get("pages", []) if isinstance(p.get("score"), (int, float))], key=lambda p: p["score"])
    cards = ""
    for p in scored[:60]:
        col = "#e5544b" if p["score"] < 55 else "#e0913a" if p["score"] < 70 else "#b9a15a"
        short = esc(urlparse(p["url"]).path or "/")
        ledger = "".join(dcard(s, x, brand) for s, x in p.get("ranked_fixes", [])[:6]) or '<div class="empty">Citation-ready.</div>'
        cards += f'<div class="page"><button class="page-head" onclick="this.parentElement.classList.toggle(\'open\')"><span class="pscore" style="--c:{col}">{p["score"]}</span><span class="ptype">{esc(p.get("type",""))}</span><span class="purl">{short}</span><span class="chev">\u25be</span></button><div class="page-body">{ledger}<a class="visit" href="{esc(p["url"])}" target="_blank" rel="noopener">open page \u2197</a></div></div>'
    extra = scored[60:]
    extra_rows = "".join(f'<tr><td>{p["score"]}</td><td>{esc(p.get("type",""))}</td><td>{esc(urlparse(p["url"]).path)}</td></tr>' for p in extra)
    extra_html = f'<details class="more"><summary>{len(extra)} more pages</summary><table class="ptable"><tr><th>Score</th><th>Type</th><th>Page</th></tr>{extra_rows}</table></details>' if extra else ""
    errs = [p for p in cr.get("pages", []) if p.get("error")]
    err_note = f'<p class="muted">{len(errs)} page(s) could not be fetched this run.</p>' if errs else ""
    if content.get("post_day") and content.get("rendered"):
        chtml = f"<pre class='draft'>{esc(content['rendered'])}</pre>"
    elif content.get("post_day"):
        chtml = "<div class='muted'>Post day \u2014 queue is empty.</div>"
    else:
        chtml = f"<div class='muted'>No post scheduled today. Next: {esc(content.get('next','\u2014'))}.</div>"
    mode = esc(cr.get("mode", ""))
    return PAGE.format(brand=brand, url=esc(cr["base"]), generated=esc(cr["generated"]),
        gsc_section=render_gsc(gsc),
        avg_ring=ring(cr.get("avg_score"), "Avg readiness", f"{cr.get('audited',0)} pages \u00b7 {mode}"),
        geo_ring=ring(geo, "GEO score", "rigorous 47-method" if geo is not None else "run pipeline"),
        cite_ring=ring((cited/total*100) if total else None, "Cited by AI", cite_txt),
        coverage=f"{cr.get('audited',0)} of {cr.get('sitemap_total',0)} sitemap URLs audited ({mode} run)",
        sitewide_band=band, issue_rows=rows, page_cards=cards or '<div class="empty">No pages scored.</div>',
        extra=extra_html, err_note=err_note, content_html=chtml)


def render_single(cfg):
    _sys.path.insert(0, str(HERE)); import aeo_agent
    try:
        rep = aeo_agent.run(cfg["url"], brand=cfg["brand"], category=cfg.get("topic", ""), live=False)
    except SystemExit:
        rep = {"score": None, "ranked_fixes": []}
    cr = {"brand": cfg["brand"], "domain": cfg["domain"], "base": cfg["url"],
          "generated": dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
          "mode": "homepage", "audited": 1, "sitemap_total": 1, "avg_score": rep.get("score"),
          "domain_sections": {}, "sitewide_issues": [],
          "pages": [{"url": cfg["url"], "type": "home", "score": rep.get("score"), "ranked_fixes": rep.get("ranked_fixes", [])}]}
    from connectors import content as cm
    return render_site(cr, cm.todays_draft(HERE / "content.config.json"))


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{brand} — Doubt Ledger</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,500&family=Jost:wght@300;400;500&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0a0a0a;--ink:#f5f1ea;--line:rgba(245,241,234,.12);--glass:rgba(245,241,234,.035);--muted:rgba(245,241,234,.55)}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:'Jost',sans-serif;font-weight:300;line-height:1.6;background-image:radial-gradient(1200px 600px at 70% -10%,rgba(245,241,234,.05),transparent)}}
.wrap{{max-width:960px;margin:0 auto;padding:48px 24px 96px}}
h1{{font-family:'Cormorant Garamond',serif;font-weight:400;font-size:44px;line-height:1.05;margin:18px 0 0}}h1 em{{font-style:italic;font-weight:500}}
.eyebrow{{font-family:'Jost';font-size:11px;letter-spacing:.28em;text-transform:uppercase;color:var(--muted)}}
.rule{{height:1px;background:var(--line);margin:14px 0 0}}.meta{{color:var(--muted);font-size:13px;margin-top:10px}}
.rings{{display:flex;gap:18px;flex-wrap:wrap;margin:36px 0 8px}}
.ring{{flex:1;min-width:150px;background:var(--glass);border:1px solid var(--line);border-radius:18px;padding:22px 18px;text-align:center;backdrop-filter:blur(8px)}}
.ring svg{{width:112px;height:112px;transform:rotate(-90deg)}}.ring-bg{{fill:none;stroke:var(--line);stroke-width:8}}.ring-fg{{fill:none;stroke:var(--ink);stroke-width:8;stroke-linecap:round;transition:stroke-dashoffset 1s}}
.ring-num{{font-family:'Cormorant Garamond';font-size:34px;margin-top:-74px;margin-bottom:34px}}.ring-num span{{font-size:15px;color:var(--muted)}}
.ring-label{{font-size:12px;letter-spacing:.2em;text-transform:uppercase}}.ring-sub{{font-size:12px;color:var(--muted);margin-top:2px}}
section{{margin-top:44px}}.coverage{{color:var(--muted);font-size:14px;margin-top:6px}}
.doubt,.page{{border:1px solid var(--line);border-radius:14px;margin:12px 0;background:var(--glass);overflow:hidden}}
.doubt-head,.page-head{{width:100%;text-align:left;background:none;border:0;color:var(--ink);cursor:pointer;display:flex;align-items:center;gap:14px;padding:15px 18px;font-family:'Jost';font-size:15px}}
.sev{{font-size:10px;letter-spacing:.14em;padding:4px 9px;border-radius:99px;border:1px solid var(--c);color:var(--c);white-space:nowrap}}
.doubt-q{{font-family:'Cormorant Garamond';font-style:italic;font-size:20px;flex:1}}
.chev{{color:var(--muted);transition:transform .25s}}.doubt.open .chev,.page.open .chev{{transform:rotate(180deg)}}
.doubt-body,.page-body{{max-height:0;overflow:hidden;transition:max-height .35s;padding:0 18px}}
.doubt.open .doubt-body{{max-height:460px;padding-bottom:16px}}.page.open .page-body{{max-height:2600px;padding-bottom:16px}}
.row{{display:flex;gap:16px;padding:9px 0;border-top:1px solid var(--line)}}.row .k{{flex:0 0 108px;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);padding-top:3px}}.row .v{{flex:1;font-size:15px}}
.row.subtract{{background:rgba(245,241,234,.04);margin:6px -18px 0;padding:12px 18px;border-radius:0 0 12px 12px}}
.pscore{{font-family:'Cormorant Garamond';font-size:26px;color:var(--c);flex:0 0 42px}}
.ptype{{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);border:1px solid var(--line);border-radius:99px;padding:3px 8px}}
.purl{{flex:1;font-size:14px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.visit{{display:inline-block;margin-top:10px;color:var(--muted);font-size:13px}}
.issue{{display:flex;align-items:center;gap:14px;padding:12px 4px;border-bottom:1px solid var(--line)}}.issue-t{{flex:1;font-size:15px}}.issue-n{{color:var(--muted);font-size:13px;white-space:nowrap}}
.empty{{color:var(--muted);padding:16px;border:1px dashed var(--line);border-radius:12px}}.muted{{color:var(--muted);font-size:14px}}
.idx{{display:flex;gap:12px;flex-wrap:wrap;margin-top:16px}}.idxc{{flex:1;min-width:120px;background:var(--glass);border:1px solid var(--line);border-radius:14px;padding:16px;text-align:center}}
.idxc b{{font-family:'Cormorant Garamond';font-size:32px;display:block}}.idxc span{{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}}
.idxc.push{{border-color:rgba(224,145,58,.5)}}.idxc.junk{{border-color:rgba(111,125,120,.5)}}
.more{{margin-top:16px}}.more summary{{cursor:pointer;color:var(--muted);font-size:14px}}
.ptable{{width:100%;border-collapse:collapse;margin-top:12px;font-size:13px}}.ptable th,.ptable td{{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);color:var(--muted)}}
pre.draft{{white-space:pre-wrap;font-family:'Jost';font-weight:300;font-size:14px;background:var(--glass);border:1px solid var(--line);border-radius:14px;padding:20px}}
footer{{margin-top:64px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:18px}}
@media(max-width:640px){{h1{{font-size:32px}}.doubt-q{{font-size:16px}}}}
</style></head><body><div class="wrap">
<header><div class="eyebrow">Doubt Ledger · site-wide AI-citation audit</div><div class="rule"></div>
<h1>{brand} &amp; the <em>disbelief</em> between you and your next citation</h1>
<div class="meta">{url} · generated {generated} · runs daily</div></header>
<div class="rings">{avg_ring}{geo_ring}{cite_ring}</div>
<div class="coverage">{coverage}</div>
{gsc_section}
<section><div class="eyebrow">Sitewide fixes — one change helps every page</div><div class="rule"></div>{sitewide_band}</section>
<section><div class="eyebrow">Most common page issues — highest leverage first</div><div class="rule"></div>{issue_rows}</section>
<section><div class="eyebrow">Weakest pages — work top to bottom</div><div class="rule"></div>
<p class="muted" style="margin-top:12px">Lowest-scoring pages first. Open any page for its own Doubt Ledger.</p>{err_note}{page_cards}{extra}</section>
<section><div class="eyebrow">Today's post — draft only</div><div class="rule"></div>{content_html}</section>
<footer>Nothing here was published, deployed, or changed. Read-only view of the daily audit.</footer>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--config"); a = ap.parse_args()
    cfg = load(Path(a.config or (HERE / "myna.config.json"))) or _sys.exit("config not found")
    cr = load(HERE / "crawl-results.json")
    if cr and cr.get("pages"):
        from connectors import content as cm
        out = render_site(cr, cm.todays_draft(HERE / "content.config.json"))
    else:
        out = render_single(cfg)
    (OUT / "index.html").write_text(out, encoding="utf-8")
    print(f"Dashboard written -> {OUT/'index.html'}")


if __name__ == "__main__":
    main()
