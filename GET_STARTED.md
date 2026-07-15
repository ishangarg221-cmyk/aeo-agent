# GET STARTED — MYNA AEO Agent

Goal of your first run: see one morning digest. No API keys needed. ~5 minutes.

## 0. You need Python 3.10 or newer
Check:  `python3 --version`   (Windows: `python --version`)
If missing, install from https://python.org (tick "Add Python to PATH" on Windows).

## 1. Open a terminal IN this folder
- Mac: right-click the `aeo-agent` folder → "New Terminal at Folder".
- Windows: open the folder, click the address bar, type `cmd`, Enter.
- Or `cd` to wherever you unzipped it, e.g. `cd ~/Downloads/aeo-agent`.

## 2. Make a clean environment (avoids all "pip" headaches)
Mac/Linux:
    python3 -m venv .venv
    source .venv/bin/activate
Windows:
    python -m venv .venv
    .venv\Scripts\activate
(Your prompt now shows `(.venv)`.)

## 3. Install
    pip install -r requirements.txt

## 4. Run your first digest
    python morning_digest.py
You'll see a report with AEO scores, a "Shopify: not connected" line (expected),
and today's post draft. It also saves `digest/<date>.md`.

That's the whole first run. Everything below is optional upgrades.

## 5. (Optional) Real AI-citation check
    Mac/Linux:  export PERPLEXITY_API_KEY=your_key
    Windows:    set PERPLEXITY_API_KEY=your_key
    python morning_digest.py

## 6. (Optional) Shopify sales + stock in the digest
Create a Shopify Admin API token (scopes: read_orders, read_products), then:
    export SHOPIFY_STORE=your-store-handle
    export SHOPIFY_ADMIN_TOKEN=shpat_...
(Windows: use `set` instead of `export`.)

## 7. (Optional) Run it automatically at 9am — see README.md → GitHub Actions.

Stuck? Copy the exact terminal output and send it back.
