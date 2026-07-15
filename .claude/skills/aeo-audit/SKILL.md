---
name: aeo-audit
description: >
  Answer/Generative Engine Optimization audit methodology. Use when auditing a page
  or site for AI-citation readiness (ChatGPT, Perplexity, Gemini, Claude, Google AI
  Overviews), fixing llms.txt / robots.txt / JSON-LD schema, writing direct-answer
  content blocks, or planning citation-earning content. Pairs with aeo_agent.py.
---

# AEO Audit Skill

Getting cited by an AI answer engine is a three-gate problem. A page only earns a
citation if it passes ALL THREE. Audit and fix them in this order.

## Gate 1 — Can the engine REACH it? (Crawlability)
- `robots.txt` must not `Disallow: /` for AI user-agents: GPTBot, OAI-SearchBot,
  ChatGPT-User, PerplexityBot, ClaudeBot, Google-Extended, CCBot, Applebot-Extended.
- Blocking any of these = that engine can never cite you. Highest-priority check.
- Content must be in server-rendered HTML. If it only appears after JS hydration,
  most crawlers won't see it. Verify with "view source", not the rendered DOM.

## Gate 2 — Can the engine UNDERSTAND it? (Structure + entity)
- **JSON-LD schema** resolves entities and facts. Minimum for a store:
  `Organization` (+ `sameAs` to socials/marketplaces), `Product`, `BreadcrumbList`,
  `FAQPage`. FAQPage directly feeds AI Overviews and Perplexity answers.
- **llms.txt** at the root: a markdown index of priority pages with 1-line
  descriptions. Cheap, high-leverage, increasingly respected.
- **Consistent entity signals**: same brand name, address, founding facts across
  site + Google Business + marketplaces. Contradictions make AI distrust the entity.

## Gate 3 — Will the engine QUOTE it? (Answer structure)
LLMs lift *passages*, not pages. The most-cited pattern:
1. A **question-style heading** (H2/H3) that matches how buyers ask
   ("Does gold-plated jewellery tarnish?").
2. A **direct answer in 40–60 words** immediately underneath — claim first,
   nuance after. This is the block that gets quoted.
3. Supporting **lists / comparison tables** — engines lift these verbatim.
4. Specific, checkable facts (materials, timeframes, prices) beat marketing adjectives.

## Doubt-Engineer content rule
Each answer block should **subtract one specific buyer disbelief**. Lead the answer
with the resolution of the doubt, then the evidence. "Growth is the subtraction of
disbelief" — the same applies to earning a citation: the engine cites the source
that most cleanly resolves the user's implicit doubt.

## Deliverables must be complete
Never hand back a schema stub or half an llms.txt. Output the full, valid,
copy-paste-ready file. Validate JSON-LD mentally against schema.org before shipping.

## Verification loop
AI indexes refresh over weeks, not minutes. After shipping fixes, re-run the live
citation check (`aeo_agent.py --brand ... --live`) at 2 and 4 weeks. Track: is the
brand *mentioned*, in what *position*, and is the *domain cited* (Perplexity Sonar
returns real source URLs — the ground truth for "did we earn the citation").

## Reference research
- Princeton/Georgia Tech "GEO: Generative Engine Optimization" (KDD 2024) — the
  original study on which content edits raise LLM citation rates.
- AutoGEO (ICLR 2026) — automated learning of generative-engine preferences.
