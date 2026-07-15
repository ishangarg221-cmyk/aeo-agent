#!/usr/bin/env python3
"""
AEO Agent — Answer/Generative Engine Optimization auditor
=========================================================
Scores a page 0–100 on how likely ChatGPT, Perplexity, Gemini, Claude and
Google AI Overviews are to CRAWL, UNDERSTAND and CITE it — then prints the
exact fixes, ranked by impact.

Built for Ishan Garg (Aavivvi) — reusable across MYNA and client sites.

Usage
-----
    python aeo_agent.py https://artificialjewellers.com
    python aeo_agent.py https://artificialjewellers.com --json report.json
    python aeo_agent.py https://example.com --brand "MYNA" --live   # live citation check

Live citation check (optional) reads whichever key is set:
    export PERPLEXITY_API_KEY=...   # best: returns real source URLs
    export OPENAI_API_KEY=...       # parametric brand knowledge
    export ANTHROPIC_API_KEY=...    # parametric brand knowledge

Dependencies: requests, beautifulsoup4
    pip install requests beautifulsoup4
"""
from __future__ import annotations
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse, json, os, re, sys
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Missing deps. Run: pip install requests beautifulsoup4")

UA = "Mozilla/5.0 (compatible; AEO-Agent/1.0; +https://aavivvi.com)"
AI_BOTS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "PerplexityBot",
           "Perplexity-User", "ClaudeBot", "Claude-User", "Google-Extended",
           "CCBot", "Amazonbot", "Applebot-Extended", "Bytespider"]
TIMEOUT = 20


# ---------------------------------------------------------------- fetch layer
def fetch(url: str):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT, allow_redirects=True)
        return r
    except requests.RequestException as e:
        return e


def get_text(url: str) -> str | None:
    r = fetch(url)
    if isinstance(r, requests.Response) and r.status_code == 200:
        return r.text
    return None


# ------------------------------------------------------------- signal checks
def check_crawlability(base: str) -> dict:
    """robots.txt AI-bot rules — if AI crawlers are blocked, nothing else matters."""
    out = {"score": 0, "max": 20, "findings": [], "fixes": []}
    robots = get_text(urljoin(base, "/robots.txt")) or ""
    blocked = []
    lines = [l.strip() for l in robots.splitlines()]
    current_agents: list[str] = []
    for line in lines:
        low = line.lower()
        if low.startswith("user-agent:"):
            current_agents = [line.split(":", 1)[1].strip()]
        elif low.startswith("disallow:"):
            path = line.split(":", 1)[1].strip()
            for a in current_agents:
                if a in AI_BOTS and path == "/":
                    blocked.append(a)
    if not robots:
        out["findings"].append("No robots.txt found (crawlers allowed by default — OK, but you have no control).")
        out["score"] = 14
        out["fixes"].append(("MEDIUM", "Add a robots.txt that explicitly ALLOWs AI bots (GPTBot, PerplexityBot, ClaudeBot, Google-Extended) so you control access on record."))
    elif blocked:
        out["findings"].append(f"AI crawlers BLOCKED in robots.txt: {', '.join(sorted(set(blocked)))}. These engines cannot cite you.")
        out["score"] = 2
        out["fixes"].append(("CRITICAL", f"Unblock AI bots in robots.txt — currently disallowing {', '.join(sorted(set(blocked)))}. This is a hard citation blocker."))
    else:
        out["findings"].append("AI crawlers are allowed by robots.txt.")
        out["score"] = 20
    return out


def check_llms_txt(base: str) -> dict:
    """llms.txt — the emerging 'sitemap for LLMs'. Presence + depth."""
    out = {"score": 0, "max": 10, "findings": [], "fixes": []}
    body = get_text(urljoin(base, "/llms.txt"))
    if not body:
        out["findings"].append("No /llms.txt — AI engines have no curated map of your key pages.")
        out["fixes"].append(("HIGH", "Publish /llms.txt: a markdown index of your most important pages (products, about, FAQ, policies) with 1-line descriptions. This is one of the highest-leverage low-effort AEO wins."))
    else:
        links = body.count("](")
        has_headings = body.strip().startswith("#")
        if links >= 5 and has_headings:
            out["score"] = 10
            out["findings"].append(f"/llms.txt present and structured ({links} links).")
        else:
            out["score"] = 5
            out["findings"].append("/llms.txt present but thin.")
            out["fixes"].append(("MEDIUM", "Deepen /llms.txt: proper markdown headings + 5+ annotated links to your priority pages."))
    return out


def _collect_jsonld(soup: BeautifulSoup) -> list:
    blocks = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
            blocks.extend(data if isinstance(data, list) else [data])
        except Exception:
            continue
    return blocks


def _types(blocks: list) -> set:
    found = set()
    for b in blocks:
        t = b.get("@type") if isinstance(b, dict) else None
        if isinstance(t, list):
            found.update(t)
        elif t:
            found.add(t)
        # nested @graph
        if isinstance(b, dict) and isinstance(b.get("@graph"), list):
            found |= _types(b["@graph"])
    return found


def check_schema(soup: BeautifulSoup) -> dict:
    """JSON-LD structured data — how AI engines resolve entities & facts."""
    out = {"score": 0, "max": 20, "findings": [], "fixes": []}
    blocks = _collect_jsonld(soup)
    types = _types(blocks)
    if not blocks:
        out["findings"].append("No JSON-LD structured data found.")
        out["fixes"].append(("CRITICAL", "Add JSON-LD schema. For a store: Organization + Product + BreadcrumbList + FAQPage. This is how AI engines extract facts (price, brand, material) and attribute them to YOU."))
        return out
    wanted = {"Organization": 6, "Product": 5, "FAQPage": 4, "BreadcrumbList": 2, "WebSite": 1,
              "LocalBusiness": 2, "Article": 3, "Review": 2, "AggregateRating": 2}
    for t, pts in wanted.items():
        if t in types:
            out["score"] += pts
            out["findings"].append(f"Schema present: {t}")
    out["score"] = min(out["score"], out["max"])
    missing = [t for t in ("Organization", "Product", "FAQPage", "BreadcrumbList") if t not in types]
    if missing:
        out["fixes"].append(("HIGH", f"Add missing high-value schema: {', '.join(missing)}. FAQPage in particular feeds AI Overviews and Perplexity direct answers."))
    return out


def check_answer_structure(soup: BeautifulSoup, text: str) -> dict:
    """Direct-answer, extractable structure — what LLMs actually quote."""
    out = {"score": 0, "max": 20, "findings": [], "fixes": []}
    h1 = soup.find_all("h1")
    h2 = soup.find_all("h2")
    lists = soup.find_all(["ul", "ol"])
    tables = soup.find_all("table")

    # H1 sanity
    if len(h1) == 1:
        out["score"] += 3
    else:
        out["fixes"].append(("MEDIUM", f"Use exactly one H1 (found {len(h1)}). AI parsers use it as the page's primary claim."))
    # heading depth
    if len(h2) >= 3:
        out["score"] += 4
        out["findings"].append(f"Good heading structure ({len(h2)} H2s).")
    else:
        out["fixes"].append(("HIGH", "Break content into clear H2 question-style sections. LLMs cite passages under headers that match user questions (e.g. 'Does gold plating tarnish?')."))
    # question-shaped headings
    q_heads = [h.get_text(strip=True) for h in soup.find_all(["h2", "h3"])
               if re.search(r"\?|how|what|why|which|is |does |can ", h.get_text(strip=True), re.I)]
    if q_heads:
        out["score"] += 5
        out["findings"].append(f"{len(q_heads)} question-style heading(s) — strong AEO signal.")
    else:
        out["fixes"].append(("HIGH", "Add question-style headings + a 40-60 word direct answer immediately under each. This 'answer block' pattern is the single most-cited structure in AEO research."))
    # lists / tables aid extraction
    if lists:
        out["score"] += 4
    else:
        out["fixes"].append(("MEDIUM", "Add scannable lists / comparison tables — AI engines lift these verbatim into answers."))
    if tables:
        out["score"] += 4
        out["findings"].append("Comparison table(s) present.")
    out["score"] = min(out["score"], out["max"])
    return out


def check_extractability(soup: BeautifulSoup, resp_text: str) -> dict:
    """Is the substance in server-rendered HTML, or hidden behind JS?"""
    out = {"score": 0, "max": 15, "findings": [], "fixes": []}
    for t in soup(["script", "style", "noscript"]):
        t.extract()
    visible = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    words = len(visible.split())
    ratio = len(visible) / max(len(resp_text), 1)
    if words >= 300:
        out["score"] += 8
        out["findings"].append(f"{words} words of server-rendered text.")
    else:
        out["fixes"].append(("CRITICAL", f"Only {words} words in raw HTML. If content renders client-side (JS), most AI crawlers won't see it. Server-render or pre-render key content."))
    if ratio >= 0.08:
        out["score"] += 7
    else:
        out["fixes"].append(("HIGH", "Low text-to-code ratio — thin extractable content relative to markup. Increase substantive on-page copy."))
    out["score"] = min(out["score"], out["max"])
    return out


def check_meta_entity(soup: BeautifulSoup, base: str) -> dict:
    """Title, meta description, canonical, entity consistency signals."""
    out = {"score": 0, "max": 15, "findings": [], "fixes": []}
    title = (soup.title.string or "").strip() if soup.title else ""
    desc = soup.find("meta", attrs={"name": "description"})
    desc = (desc.get("content") or "").strip() if desc else ""
    canonical = soup.find("link", attrs={"rel": "canonical"})
    if 15 <= len(title) <= 65:
        out["score"] += 4
    else:
        out["fixes"].append(("MEDIUM", f"Title is {len(title)} chars — aim 15-65 with the brand + primary entity."))
    if 50 <= len(desc) <= 165:
        out["score"] += 4
    else:
        out["fixes"].append(("MEDIUM", "Write a 50-165 char meta description stating what the page factually is."))
    if canonical:
        out["score"] += 3
    else:
        out["fixes"].append(("LOW", "Add a canonical link to consolidate entity signals."))
    # sameAs / org consistency hint
    if "sameas" in (resp := str(soup)).lower() or "organization" in resp.lower():
        out["score"] += 4
        out["findings"].append("Entity/sameAs signals detected.")
    else:
        out["fixes"].append(("HIGH", "Add Organization schema with sameAs links to your social/marketplace profiles — this is how AI engines confirm you're a real, consistent entity."))
    out["score"] = min(out["score"], out["max"])
    return out


# ------------------------------------------------------- optional live check
def live_citation_check(brand: str, category: str) -> dict | None:
    prompts = [
        f"What are the best {category} brands?",
        f"Recommend a {category} brand for online shoppers.",
        f"Tell me about {brand}.",
    ]
    if os.getenv("PERPLEXITY_API_KEY"):
        return _perplexity(brand, prompts)
    if os.getenv("OPENAI_API_KEY"):
        return _openai(brand, prompts)
    if os.getenv("ANTHROPIC_API_KEY"):
        return _anthropic(brand, prompts)
    return None


def _mentions(brand, text):
    return brand.lower() in (text or "").lower()


def _perplexity(brand, prompts):
    res = {"engine": "Perplexity (sonar)", "results": []}
    for p in prompts:
        try:
            r = requests.post("https://api.perplexity.ai/chat/completions",
                headers={"Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}"},
                json={"model": "sonar", "messages": [{"role": "user", "content": p}]},
                timeout=40).json()
            msg = r["choices"][0]["message"]["content"]
            cites = r.get("citations", [])
            res["results"].append({"prompt": p, "mentioned": _mentions(brand, msg),
                                   "cited_domain": any(brand.lower() in c.lower() for c in cites),
                                   "sources": cites[:5]})
        except Exception as e:
            res["results"].append({"prompt": p, "error": str(e)})
    return res


def _openai(brand, prompts):
    res = {"engine": "OpenAI (parametric)", "results": []}
    for p in prompts:
        try:
            r = requests.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": p}]},
                timeout=40).json()
            msg = r["choices"][0]["message"]["content"]
            res["results"].append({"prompt": p, "mentioned": _mentions(brand, msg)})
        except Exception as e:
            res["results"].append({"prompt": p, "error": str(e)})
    return res


def _anthropic(brand, prompts):
    res = {"engine": "Anthropic (parametric)", "results": []}
    for p in prompts:
        try:
            r = requests.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                         "anthropic-version": "2023-06-01"},
                json={"model": "claude-sonnet-4-5", "max_tokens": 512,
                      "messages": [{"role": "user", "content": p}]},
                timeout=40).json()
            msg = "".join(b.get("text", "") for b in r.get("content", []))
            res["results"].append({"prompt": p, "mentioned": _mentions(brand, msg)})
        except Exception as e:
            res["results"].append({"prompt": p, "error": str(e)})
    return res


# ----------------------------------------------------------------- reporting
def bar(score, width=28):
    filled = int(round(score / 100 * width))
    return "█" * filled + "░" * (width - filled)


def grade(s):
    return ("A — citation-ready" if s >= 85 else "B — strong, minor gaps" if s >= 70 else
            "C — visible but leaking citations" if s >= 55 else
            "D — hard to cite" if s >= 40 else "F — effectively invisible to AI")


def run(url, brand=None, category="fashion jewellery", live=False):
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    resp = fetch(url)
    if not isinstance(resp, requests.Response) or resp.status_code != 200:
        sys.exit(f"Could not fetch {url} ({resp if not isinstance(resp, requests.Response) else resp.status_code})")
    soup = BeautifulSoup(resp.text, "html.parser")

    sections = {
        "Crawlability (AI bots)": check_crawlability(base),
        "llms.txt": check_llms_txt(base),
        "Structured data / schema": check_schema(soup),
        "Answer structure": check_answer_structure(soup, resp.text),
        "Content extractability": check_extractability(soup, resp.text),
        "Meta & entity signals": check_meta_entity(soup, base),
    }
    total = sum(s["score"] for s in sections.values())
    maxt = sum(s["max"] for s in sections.values())
    pct = round(total / maxt * 100)

    print("\n" + "═" * 60)
    print(f"  AEO AUDIT · {url}")
    print("═" * 60)
    print(f"  SCORE  {pct}/100   [{bar(pct)}]")
    print(f"  GRADE  {grade(pct)}")
    print("═" * 60)
    for name, s in sections.items():
        print(f"\n  {name:<30} {s['score']:>2}/{s['max']}")
        for f in s["findings"]:
            print(f"      ✓ {f}")
    # ranked fixes
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    fixes = [f for s in sections.values() for f in s["fixes"]]
    fixes.sort(key=lambda x: order.get(x[0], 9))
    print("\n" + "─" * 60)
    print("  PRIORITISED FIXES")
    print("─" * 60)
    for i, (sev, fix) in enumerate(fixes, 1):
        print(f"  {i}. [{sev}] {fix}")

    live_out = None
    if live:
        if not brand:
            print("\n  (Live check skipped: pass --brand to name the brand to test.)")
        else:
            live_out = live_citation_check(brand, category)
            print("\n" + "─" * 60)
            print("  LIVE CITATION CHECK")
            print("─" * 60)
            if not live_out:
                print("  No API key set. export PERPLEXITY_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY to enable.")
            else:
                print(f"  Engine: {live_out['engine']}")
                for r in live_out["results"]:
                    if "error" in r:
                        print(f"    ⚠ {r['prompt']} → {r['error']}")
                    else:
                        m = "MENTIONED" if r.get("mentioned") else "not mentioned"
                        extra = " + cited domain" if r.get("cited_domain") else ""
                        print(f"    • {r['prompt']}\n        → {m}{extra}")
    print()
    return {"url": url, "score": pct, "grade": grade(pct),
            "sections": {k: {kk: vv for kk, vv in v.items()} for k, v in sections.items()},
            "ranked_fixes": fixes, "live": live_out}


def main():
    ap = argparse.ArgumentParser(description="AEO Agent — AI-citation readiness auditor")
    ap.add_argument("url")
    ap.add_argument("--brand", help="Brand name for the live citation check")
    ap.add_argument("--category", default="fashion jewellery", help="Category for live prompts")
    ap.add_argument("--live", action="store_true", help="Run live AI citation check (needs API key)")
    ap.add_argument("--json", metavar="FILE", help="Write full report as JSON")
    a = ap.parse_args()
    report = run(a.url, a.brand, a.category, a.live)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"  Report written to {a.json}\n")


if __name__ == "__main__":
    main()
