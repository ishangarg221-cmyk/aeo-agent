# AEO Agent — MYNA AI-Citation Stack

One command runs three loops against a site and saves a trackable baseline:

- **WRITE** — MYNA-rules-aware readiness audit + fixes (`aeo_agent.py`, your agent)
- **SCORE** — rigorous 47-method GEO score (`geo audit`, from geo-optimizer-skill)
- **PROVE** — real proof the brand is cited by ChatGPT/Perplexity (`geo citations`)

The whole point: most tools stop at "you *should* get cited." This stack closes the
loop to "here's proof you *were* cited — or that a competitor was instead."

## Setup
```bash
pip install -r requirements.txt        # requests, beautifulsoup4, geo-optimizer-skill
export PERPLEXITY_API_KEY=...           # enables the real citation check (recommended)
```

## Run it — one command
```bash
./run.sh                                # MYNA baseline (uses myna.config.json)
./run.sh --config client.json           # reuse for a client site
./run.sh --no-citations                 # readiness scores only, skip the live check
```
Each run prints both scores + the citation result, and saves
`baselines/<domain>_<UTC>.json`. Run again in 2–4 weeks and it prints the deltas
automatically — that's your repeatable baseline.

### The MYNA baseline (myna.config.json)
Pre-loaded with MYNA (artificialjewellers.com) and five **doubt-engineered** buyer
queries — the exact disbeliefs the citation check tests whether MYNA resolves:
tarnish, zinc-alloy quality, real-brand-vs-reseller, anti-tarnish, trust. Edit the
`citation_queries` list to change what you test.

## Claude Code
```
your-project/
├── .mcp.json                       # exposes geo tools (geo_audit, geo_citations, geo_fix…)
└── .claude/
    ├── agents/aeo-seo-agent.md     # the agent that drives ./run.sh + geo MCP tools
    └── skills/aeo-audit/SKILL.md   # the methodology
```
Then: `> use the aeo-seo-agent to audit and fix artificialjewellers.com`

## Adding more GitHub skills (the governed way)
See `skills/README.md` and `skills/registry.json`. Two gates, both required:
1. **Maintained** (commit within ~90 days + tests/releases).
2. **Closes a new loop.** WRITE/SCORE/PROVE are taken. Worth adding: off-site
   **authority** tracking, **competitor** share-of-voice, **content decay**.
   Reject duplicate scorers — they add noise, not signal.

If the new skill has a JSON-emitting CLI, register its command in
`myna.config.json → extra_tools` (`enabled: true`) and it runs as step [4] of the
pipeline — no code changes. Log the decision in `registry.json`.

## Files
```
aeo_agent.py        MYNA auditor (WRITE)          run.sh            one-command wrapper
aeo_pipeline.py     orchestrator (all loops)      myna.config.json  MYNA baseline config
.mcp.json           geo tools for Claude Code     baselines/        timestamped snapshots
skills/registry.json  governed skill list         skills/README.md  how to add skills
.claude/            agent + methodology
```

## The one honest limit
No skill can manufacture off-site authority (Reddit, Wikipedia, third-party "best of"
lists). This stack wins the technical half of a citation and proves the result; the
earned-mention half is your Doubt-Engineer content + PR strategy. Anyone selling a repo
as a complete citation solution is overpromising.

---

## Daily automation (the agent that runs itself)
`daily_run.py` does the whole **read → analyze → draft** loop every day with **zero
live writes**. It audits, checks citations, diffs vs yesterday, stages draft fixes into
`pending-fixes/`, writes `daily-digest.md`, and exits non-zero on any regression.

**Anything that changes the live site is gated behind your approval** — see `tasks.md`
for the full AUTO vs APPROVE split.

### Option A — GitHub Actions (recommended, no server)
1. Push this folder to a GitHub repo.
2. Add repo secret `PERPLEXITY_API_KEY` (Settings → Secrets → Actions).
3. `.github/workflows/daily-aeo.yml` runs daily at 03:30 UTC (09:00 IST). Each run
   uploads the digest + baseline as an artifact and, if fixes were staged, **opens a
   Pull Request**. Review the PR, merge to approve. Nothing deploys on its own.

### Option B — local cron
```bash
30 3 * * *  cd /path/to/aeo-agent && PERPLEXITY_API_KEY=... python3 daily_run.py >> daily.log 2>&1
```

### Run it once by hand
```bash
python3 daily_run.py            # MYNA;  --config client.json for a client
```

---

## The 9am morning digest (drafts only)
`morning_digest.py` is the top-level daily agent. It runs the AEO job, pulls Shopify
(read-only), and drafts today's M/W/F post — then folds all of it into **one**
`digest/<date>.md`. Nothing publishes; see `tasks.md` for the AUTO/APPROVE split.

### Run it
```bash
python3 morning_digest.py            # MYNA;  --config client.json for a client
```

### Connect Shopify (optional, read-only)
Create an Admin API access token in Shopify (scopes: `read_orders`, `read_products`), then:
```bash
export SHOPIFY_STORE=your-store-handle       # the *.myshopify.com prefix
export SHOPIFY_ADMIN_TOKEN=shpat_...
```
Without these, the Shopify section simply says "not connected" — everything else still runs.

### Email the digest (optional)
```bash
export SMTP_HOST=smtp.gmail.com SMTP_USER=you@gmail.com SMTP_PASS=app_password DIGEST_TO=you@gmail.com
```

### Content queue
Edit `content.config.json` — add posts to `queue`, set `_drafted: true` after you publish
one so the agent advances to the next. MYNA is the only nameable brand.

### Scheduled (GitHub Actions)
`.github/workflows/daily-aeo.yml` runs it daily at 09:00 IST, uploads the digest, emails it
(if SMTP secrets set), and opens a review PR for any staged fixes.

---

## Site-wide audit (every page)
`crawl_site.py` reads your `sitemap.xml`, audits every product/collection/page, and
writes `crawl-results.json`. The dashboard then shows a site overview + per-page
drill-down. Cadence is automatic in the workflow: **top priority pages daily, the
full sitemap on Sundays.** Set your daily pages in `myna.config.json → priority_pages`
(leave empty to auto-pick homepage + first 20). Run manually:
```
python crawl_site.py --mode daily     # or: --mode weekly
python build_dashboard.py
```
