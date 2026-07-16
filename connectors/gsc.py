"""
Google Search Console connector.
================================
Two ways in, both supported:
  • API mode    — a Google service-account JSON (full: analytics + sitemaps +
                  per-URL index inspection). Set GSC_CREDENTIALS_JSON (path or raw
                  JSON) and gsc_property in the config.
  • CSV mode    — drop GSC's manual exports into gsc-exports/ (analytics only, but
                  instant, no setup). Files: queries.csv, pages.csv, countries.csv,
                  and optionally not-indexed.csv (the Pages report export).

Everything read-only except submit_sitemap(), which is an explicit, opt-in write.
"""
from __future__ import annotations
import csv
import datetime as dt
import json
import os
from pathlib import Path
from urllib.parse import urlparse

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    _HAVE_API = True
except Exception:
    _HAVE_API = False

SCOPES = ["https://www.googleapis.com/auth/webmasters"]


# --------------------------------------------------------------- junk heuristics
JUNK_MARKERS = ("?", "/cart", "/account", "/checkout", "/search", "/challenge",
                "variant=", "sort_by=", "filter.", "?page=", "/feed", ".atom",
                "/collections/all?", "grid_list", "/tools/")


def classify_url(url: str) -> str:
    """'junk' (Google is right to skip), 'value' (should be indexed), or 'other'."""
    u = url.lower()
    p = urlparse(u)
    if any(m in u for m in JUNK_MARKERS):
        return "junk"
    # a product reached via a collection path is a duplicate of /products/<handle>
    if "/collections/" in p.path and "/products/" in p.path:
        return "junk"
    if any(k in p.path for k in ("/products/", "/collections/", "/pages/", "/blogs/")) or p.path in ("", "/"):
        return "value"
    return "other"


# coverageState -> (bucket, what to do)
COVERAGE_ADVICE = {
    "submitted and indexed": ("indexed", "Indexed — good."),
    "indexed, not submitted in sitemap": ("indexed", "Indexed, but add it to your sitemap."),
    "crawled - currently not indexed": ("fix", "Thin/low-value in Google's eyes. Beef up unique content + add internal links, then Request Indexing."),
    "discovered - currently not indexed": ("fix", "Google found it but hasn't crawled — usually weak internal linking / crawl budget. Link to it from indexed pages; ensure it's in the sitemap."),
    "duplicate without user-selected canonical": ("canonical", "Duplicate. Set a canonical tag (or noindex if it's a variant)."),
    "duplicate, google chose different canonical than user": ("canonical", "Google picked a different canonical. Align your canonical tag."),
    "alternate page with proper canonical tag": ("ok-skip", "Expected — a variant pointing to its canonical. Leave it."),
    "excluded by 'noindex' tag": ("noindex", "Has a noindex tag. If this page is valuable, remove the noindex."),
    "blocked by robots.txt": ("robots", "Blocked in robots.txt. Unblock if valuable."),
    "page with redirect": ("ok-skip", "Redirect — expected, leave it."),
    "not found (404)": ("remove", "404 — remove from sitemap / fix the link."),
    "soft 404": ("fix", "Soft 404 — the page looks empty to Google. Add real content."),
    "blocked due to unauthorized request (401)": ("fix", "Auth-blocked — make it public if valuable."),
}


def advise_coverage(state: str) -> tuple[str, str]:
    return COVERAGE_ADVICE.get((state or "").strip().lower(), ("review", f"Review manually: {state}"))


# ------------------------------------------------------------------- the client
class GSC:
    def __init__(self, property_url: str):
        self.property = property_url            # e.g. sc-domain:artificialjewellers.com
        self.svc = None
        if _HAVE_API:
            self._auth()

    def _auth(self):
        raw = os.getenv("GSC_CREDENTIALS_JSON", "").strip()
        info = None
        if raw.startswith("{"):
            info = json.loads(raw)
        elif raw and Path(raw).exists():
            info = json.loads(Path(raw).read_text())
        elif Path("google-service-account.json").exists():
            info = json.loads(Path("google-service-account.json").read_text())
        if not info:
            return
        try:
            creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            self.svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        except Exception:
            self.svc = None

    @property
    def connected(self) -> bool:
        return self.svc is not None

    # ---- analytics -------------------------------------------------------
    def query(self, dimensions, days=28, row_limit=1000, filters=None):
        if not self.svc:
            return []
        end = dt.date.today()
        start = end - dt.timedelta(days=days)
        body = {"startDate": start.isoformat(), "endDate": end.isoformat(),
                "dimensions": dimensions, "rowLimit": row_limit}
        if filters:
            body["dimensionFilterGroups"] = [{"filters": filters}]
        try:
            r = self.svc.searchanalytics().query(siteUrl=self.property, body=body).execute()
            return r.get("rows", [])
        except Exception as e:
            return [{"_error": str(e)}]

    def top_pages(self, days=28, n=100):
        return _rows(self.query(["page"], days, n), "page")

    def top_queries(self, days=28, n=200):
        return _rows(self.query(["query"], days, n), "query")

    def by_country(self, days=28, n=50):
        return _rows(self.query(["country"], days, n), "country")

    # ---- sitemaps --------------------------------------------------------
    def list_sitemaps(self):
        if not self.svc:
            return []
        try:
            return self.svc.sitemaps().list(siteUrl=self.property).execute().get("sitemap", [])
        except Exception as e:
            return [{"_error": str(e)}]

    def submit_sitemap(self, feedpath):          # explicit opt-in write
        if not self.svc:
            return {"_error": "not connected"}
        try:
            self.svc.sitemaps().submit(siteUrl=self.property, feedpath=feedpath).execute()
            return {"submitted": feedpath}
        except Exception as e:
            return {"_error": str(e)}

    # ---- index inspection ------------------------------------------------
    def inspect(self, url):
        if not self.svc:
            return {"_error": "not connected"}
        try:
            r = self.svc.urlInspection().index().inspect(
                body={"inspectionUrl": url, "siteUrl": self.property}).execute()
            res = r.get("inspectionResult", {}).get("indexStatusResult", {})
            return {"url": url,
                    "verdict": res.get("verdict"),
                    "coverageState": res.get("coverageState"),
                    "robotsTxtState": res.get("robotsTxtState"),
                    "indexingState": res.get("indexingState"),
                    "lastCrawl": res.get("lastCrawlTime")}
        except Exception as e:
            return {"url": url, "_error": str(e)}


def _rows(rows, key):
    out = []
    for r in rows or []:
        if "_error" in r:
            return r
        out.append({key: (r.get("keys") or [""])[0],
                    "clicks": r.get("clicks", 0), "impressions": r.get("impressions", 0),
                    "ctr": round(r.get("ctr", 0) * 100, 2), "position": round(r.get("position", 0), 1)})
    return out


# ------------------------------------------------------- opportunity analysis
def opportunities(pages, queries, countries):
    low_ctr = sorted(
        [p for p in pages if p["impressions"] >= 50 and p["ctr"] < 2 and p["position"] <= 20],
        key=lambda p: -p["impressions"])[:15]
    striking = sorted(
        [q for q in queries if 4 < q["position"] <= 20 and q["impressions"] >= 30],
        key=lambda q: -q["impressions"])[:20]
    top_country_clicks = sorted(countries, key=lambda c: -c["clicks"])[:1]
    country_gaps = sorted(
        [c for c in countries if c["impressions"] >= 100 and c["ctr"] < 1.5],
        key=lambda c: -c["impressions"])[:8]
    return {"low_ctr_pages": low_ctr, "striking_distance": striking,
            "country_gaps": country_gaps,
            "top_country": top_country_clicks[0] if top_country_clicks else None}


def content_plan(striking, low_ctr):
    plan = []
    for q in striking[:10]:
        plan.append({"target": q["query"], "why": f"ranks #{q['position']} with {q['impressions']} impressions/mo",
                     "action": "Create or expand a page that directly answers this query — a question-style H2 + a 40-60 word direct answer + supporting detail. You're one page from page-one."})
    for p in low_ctr[:6]:
        plan.append({"target": urlparse(p["page"]).path, "why": f"{p['impressions']} impressions but only {p['ctr']}% CTR",
                     "action": "Rewrite the title tag + meta description to match intent and add a hook. Impressions are there; the click isn't."})
    return plan


# --------------------------------------------------------------- CSV fallback
def from_csv(folder: Path):
    """Parse manually-exported GSC CSVs into the same shapes as the API."""
    def read(name, key):
        f = folder / name
        if not f.exists():
            return []
        out = []
        with f.open(encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                low = {k.lower().strip(): v for k, v in row.items()}
                val = low.get(key) or low.get(key + "s") or next(iter(low.values()), "")
                def num(*names):
                    for n in names:
                        if n in low:
                            try:
                                return float(str(low[n]).replace("%", "").replace(",", ""))
                            except Exception:
                                return 0
                    return 0
                out.append({key: val, "clicks": int(num("clicks")), "impressions": int(num("impressions")),
                            "ctr": num("ctr", "click through rate"), "position": num("position", "average position")})
        return out
    return {"pages": read("pages.csv", "page"),
            "queries": read("queries.csv", "query"),
            "countries": read("countries.csv", "country")}
