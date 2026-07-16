# Connecting Google Search Console

Two ways. Start with the fast one if you want value today.

## Option 1 — Fast: manual CSV export (no setup, ~5 min)
Gives the agent your clicks / queries / pages / countries so it can find
opportunities and build a content plan. (Index diagnosis needs Option 2.)

1. In Search Console → **Performance** → set date range to **Last 3 months**.
2. Click **Export** (top right) → **Download CSV** (or Google Sheets).
3. From the export you get several tabs/files. Rename and drop them into a folder
   called **`gsc-exports/`** in the agent, named exactly:
   - `queries.csv`  (the Queries tab)
   - `pages.csv`    (the Pages tab)
   - `countries.csv`(the Countries tab)
4. Run `python gsc_report.py`. It auto-detects CSV mode.

Downside: you re-export by hand. Good for a first look; for the self-running
dashboard use Option 2.

## Option 2 — Full: service account (auto, ~15 min, one-time)
Lets the agent pull data AND inspect index status for every page, every day,
with no manual export. This is what powers the "252 not-indexed" diagnosis.

1. Go to **console.cloud.google.com** → create a project (any name).
2. **APIs & Services → Library** → search **"Search Console API"** → **Enable**.
3. **APIs & Services → Credentials → Create credentials → Service account**.
   - Name it (e.g. `aeo-agent`), create, skip the optional roles, Done.
4. Open the service account → **Keys → Add key → Create new key → JSON** → download.
   Open the JSON, copy the **`client_email`** value (looks like
   `aeo-agent@yourproject.iam.gserviceaccount.com`).
5. In **Search Console → Settings → Users and permissions → Add user** →
   paste that `client_email` → permission **Full** (needed for URL Inspection) → Add.
6. Give the agent the key. Locally: save the JSON as `google-service-account.json`
   in the agent folder. On GitHub: repo **Settings → Secrets → Actions → New secret**,
   name `GSC_CREDENTIALS_JSON`, paste the **entire JSON file contents** as the value.
7. Confirm `gsc_property` in `myna.config.json` — for a **Domain** property it's
   `sc-domain:artificialjewellers.com` (already set).

Then every daily run pulls GSC data and inspects your pages automatically.

## What the agent will NOT do
- It can't force Google to index pages (no public API for that). It hands you the
  exact list of valuable pages to **Request Indexing** on manually, and the junk to
  noindex/remove. That per-page "Request Indexing" click stays in the GSC UI.
- Sitemap resubmit IS available but is opt-in only:
  `python gsc_report.py --submit-sitemap https://artificialjewellers.com/sitemap.xml`
