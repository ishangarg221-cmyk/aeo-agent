# Adding new GitHub skills (the governed way)

You'll keep finding skills on GitHub. Good — but add them with discipline so the
stack stays a weapon, not a junk drawer. Two gates, both must pass:

1. **Maintained?** Last commit within ~90 days, plus real tests or a release
   cadence. A dead repo is a liability (Taleb).
2. **New loop?** It must do a job none of your current skills do. The stack
   already covers **WRITE** (your agent), **SCORE** (geo audit), and **PROVE**
   (geo citations). A second scorer is noise. Open loops actually worth filling:
   off-site **authority** tracking, **competitor** share-of-voice, **content decay**.

Run every candidate through the doubt gate in `registry.json` (`_governance.doubt_gate`)
before it earns a slot.

## To wire a skill into the one-command pipeline

If the skill has a CLI that emits JSON, you don't touch any code — just register
its command in your config's `extra_tools` array and flip `enabled` to `true`.
Use the placeholders `{url} {domain} {brand} {topic}`:

```json
"extra_tools": [
  {
    "name": "authority-tracker",
    "enabled": true,
    "cmd": ["authority-cli", "scan", "--domain", "{domain}", "--format", "json"]
  }
]
```

Next `./run.sh` will run it as step [4] and fold its output into the same
timestamped baseline. Then add a matching entry to `registry.json → skills` so
the decision is on the record (what loop it closes, when you verified it).

## To expose it to Claude Code as well

If it ships an MCP server, add it to `.mcp.json` alongside `geo-optimizer`, and
mention it in `.claude/agents/aeo-seo-agent.md` so the agent knows to reach for it.
