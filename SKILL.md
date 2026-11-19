---
name: rea-seo
description: Use when someone wants to reverse engineer the #1 Google result for a keyword against their own site, "REA for SEO", "REA SEO", or a #1-vs-you teardown across on-page, agentic SEO/GEO, authority and backlinks, site structure, content and speed, ending in a plan to take the ranking.
---

# REA SEO

Inspired by REA (github.com/morluto/rea), not affiliated. REA reverse engineers software; it cannot
see schema, meta values, speed or backlinks. REA SEO does the SEO half with DataForSEO.

Built for Claude Code (the terminal or the Code tab of the Claude desktop app) on Mac, Windows or Linux.
Cost about $0.95 of DataForSEO credit per keyword. Runtime about 3 minutes.

## Paths
- `SKILL_DIR` = the folder this SKILL.md is in. Every script is `"$SKILL_DIR/scripts/<name>.py"`.
  Always quote it (paths can contain spaces).
- Runs are saved in the user's CURRENT folder: `rea-seo/<slug>/`. Never write runs inside SKILL_DIR.
- Python command: `python3` (Windows: `python` if `python3` is not found).

## Framing (non-negotiable)
Every row is a difference between two sites, never a cause. Never write "this is why Google ranks them".
Steal the strategy, never the content.

## Step 0: setup check (every first run, free)
`python3 "$SKILL_DIR/scripts/check_setup.py"`
- Missing packages: run the pip command it prints.
- Missing login: ask the user for their DataForSEO API login (app.dataforseo.com/api-access, not the
  website password) and write it to `"$SKILL_DIR/.env"` as `DATAFORSEO_USERNAME=` / `DATAFORSEO_PASSWORD=`.
  Never echo the password back in chat.
- Rerun until every line is OK. Then tell the user the run costs about $0.95 and confirm before step 1.

## Ask for (one message)
Keyword, their domain, country (2840 US, 2036 AU, 2826 UK, 2124 CA, 2152 CL; any DataForSEO location
code works), language code. Optional: their exact page URL, a specific rival URL.

## Run
1. `python3 "$SKILL_DIR/scripts/collect.py" --keyword "<kw>" --site <domain> [--page <url>] --location <code> --language <lang>`
   Top 10 + page data. Prints the run folder `rea-seo/<slug>`.
2. `python3 "$SKILL_DIR/scripts/teardown.py" rea-seo/<slug> [--rival <url>]`
   Deep #1 vs you. Default rival = the #1 web result. If the user's site is #1, use #2 as the rival and say so.
3. `python3 "$SKILL_DIR/scripts/report.py" rea-seo/<slug>` writes scores.json + report.html.
4. Read scores.json + teardown.json and write `rea-seo/<slug>/plan.json` (schema below).
5. Rerun step 3 (the report now includes the plan), then
   `python3 "$SKILL_DIR/scripts/export.py" rea-seo/<slug>` builds `rea-seo/<slug>/package/` + a zip.
6. `python3 "$SKILL_DIR/scripts/open_report.py" rea-seo/<slug>` opens the designed report in the
   browser. Always open the package copy: its file links only work inside the package.

Do NOT rebuild, restyle or summarise the report as your own HTML or markdown page. The template in
`templates/rea_report.html` is the design; your job is the plan.json content.

## plan.json
```json
{"headline": "short verdict, max 12 words",
 "dek": "one or two sentences: where you lead, where the gap is",
 "moves": [{"tag": "week|time|keep|dont", "title": "...", "body": "...", "evidence": "the numbers",
            "steps": ["3 to 4 concrete actions"], "done_when": "...",
            "watch": "<a row label copied exactly from scores.json>", "baseline": "today's value"}]}
```
- 4 to 6 moves, ordered by impact. Check every number against the JSON. No em dashes.
- Include a "dont" move when the #1 wins despite something (do not copy that).
- Include a "keep" move for something the user already beats them on.

## Finish (chat message)
3 to 5 lines: the headline, areas won vs lost, the biggest gap with its two numbers, the path to the
package folder, and: "Drag the package folder into Claude or ChatGPT and say: work through ACTION_PLAN.md
one step at a time." Mention the actual DataForSEO cost the scripts printed.

## Known data quirks
- DataForSEO SERP urls can be google.com/goto wrappers; collect.py resolves them.
- llm_mentions `mentions` = Google AI answers mentioning the domain. `sources_domain` lists co-cited
  domains inside THAT domain's answers, so never compare one site's total to the other's co-citation count.
- DataForSEO Labs is thin for small non-English markets: trust SERP + Backlinks, treat Labs traffic as rough.
- yt-dlp is optional; without it YouTube results in the top 10 just lack view counts.
