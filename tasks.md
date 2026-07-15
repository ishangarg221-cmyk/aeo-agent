# Daily task manifest — one 9am digest, drafts only

The agent runs every morning and produces **one consolidated digest** across three
fronts. Everything is a draft or an alert. Nothing is published, deployed, or changed.

## What the 9am digest contains
| Front | In the digest (AUTO) | Held for you (APPROVE) |
|---|---|---|
| **AEO / SEO** | scores, deltas, citation status, alerts; staged fix files | deploy fixes to live site |
| **Shopify** | yesterday's sales, low-stock, thin-content PDPs, drafted schema | any product/price/PDP/review write |
| **Content** | today's M/W/F post + carousel, fully drafted | publishing to LinkedIn (do manually) |

## Hard boundaries (safety by construction)
- The Shopify connector has **no write methods** — it literally cannot change the store.
- LinkedIn is **draft-only by design** — auto-posting risks your account (ToS). The agent
  writes the post; you publish it (or schedule via Buffer/Taplio).
- Staged AEO fixes go to `pending-fixes/` (a folder) and only reach production when you
  merge the PR the workflow opens.

## Delivery
`morning_digest.py` writes `digest/<date>.md`, emails it if `SMTP_*` secrets are set,
and the GitHub Action uploads it as an artifact + opens a review PR for anything staged.

## Why drafts-only (Doubt-Engineer)
Automation should subtract your doubt, not add to it. Drafts-plus-one-approval does ~90%
of the work unattended while guaranteeing you never wake up to a change you didn't make.
