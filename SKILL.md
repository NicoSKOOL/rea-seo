---
name: rea-seo
description: Use when someone wants to know why a website (theirs or a client's) is being outranked on Google, who its real search competitors are, or wants to reverse engineer the sites ranking above it. Checks 5 to 10 keywords to find the businesses that outrank the site most often, compares it with the top 3 on Google Business Profile, authority, on-page, content, structure, AI visibility and speed, reads what kind of page Google shows, and builds a designed report (published as an artifact), an action plan and a data package. Runs on the DataForSEO MCP connector. No API keys needed.
---

# REA SEO (DataForSEO MCP edition)

Inspired by REA (github.com/morluto/rea), not affiliated. REA reverse engineers software; REA SEO
reverse engineers why a site is outranked.

All paid data comes through the user's **DataForSEO MCP connector**. The Python scripts only do free
work (pick rivals, resolve URLs, fetch public HTML, robots.txt, llms.txt, sitemaps, score, render).
Never ask for or store a DataForSEO password.

## Paths
- `SKILL_DIR` = the folder this SKILL.md is in. Scripts: `"$SKILL_DIR/scripts/<name>.py"`. Always quote it.
- Runs are saved in the user's CURRENT folder: `rea-seo/<site-slug>/` (called `<run>` below).
  Never write runs inside SKILL_DIR.
- Python: `python3` (Windows: `python` if `python3` is not found).

## Framing (non-negotiable)
Every row is a difference between sites, never a cause. Never write "this is why Google ranks them".
A gap all rivals share is evidence; one rival's quirk is not. Steal the strategy, never the content.

## DataForSEO tool names
Tools carry a server prefix that differs per install (`mcp__dfs-mcp__`, `mcp__DataForSEO__` ...).
This file uses the part after the prefix. If the tools are deferred, load them with ToolSearch first.

## Keeping MCP output small
Several tools return a lot of text. Always pass the smallest `limit` given here. When a result is
saved to a file instead of shown, read the fields you need with a short python or jq command.
Never paste raw results into chat.

## Step 0: setup (free)
1. `python3 "$SKILL_DIR/scripts/check_setup.py"`. If packages are missing, run the pip command it prints.
2. Confirm a DataForSEO tool such as `serp_organic_live_advanced` is available. If not, stop and tell
   the user to connect the DataForSEO connector (Claude desktop: Settings > Connectors) and restart.
3. Tell the user a run makes about 35 to 40 DataForSEO calls, roughly $1 to $2 of credit, and takes
   5 to 10 minutes. Confirm before spending.

## Ask for (one message, skip what was given)
Domain (required), business name, country (DataForSEO `location_name`), and for a local business the
state or city it serves. Keywords are optional: if none are given, choose them in step 1.

## Run

**1. Keywords (MCP, 1 call).** `dataforseo_labs_google_ranked_keywords` target=<domain>, limit 150,
order_by `["keyword_data.keyword_info.search_volume,desc"]`, filters
`[["ranked_serp_element.serp_item.rank_group","<=",30],"and",["keyword_data.keyword_info.search_volume",">=",50]]`.
The result is saved to a file: list it with `python3 "$SKILL_DIR/scripts/kwlist.py" <that file>`.
Pick **5 to 10 commercial keywords**:
- money terms (service + place, lender, company, near me), not questions or blog topics
- a spread: head terms, 2 or 3 specific services, 1 or 2 local terms
- at most 2 word-order variants of the same phrase
- include any keyword the user named. The **primary** keyword is the highest-volume head term where the
  site ranks 4 to 20.
Tell the user the list in one line.

**2. Start (free).**
`python3 "$SKILL_DIR/scripts/start.py" --site <domain> --brand "<Business Name>" --location "<Country>" --serp-location "<Region,Country>" --kw "<primary>=<volume>" --kw "<kw2>=<volume>" ...`
`--serp-location` is where the live results are checked. For a local business use its state or city
("South Carolina,United States"); otherwise leave it out. It prints `<run>`.

**3. Who is ahead (MCP, 1 call + free).** `dataforseo_labs_google_serp_competitors` with the keywords,
limit 30. Write `<run>/competitors.json`, one line per returned domain (include the user's own domain),
positions in the same order as the `--kw` arguments, null where the domain has no position:
```json
{"positions": {"example.com": [12, 13, null, 8], "www.rival.com": [7, 10, 9, 3]}}
```
Then `python3 "$SKILL_DIR/scripts/rivals.py" <run>`. It prints a leaderboard (keywords where each
domain is ahead of the site) and stars 3 rivals. **Check the stars.** Keep the business that is ahead
most often, then prefer like-for-like businesses (same kind of company, same market, similar size)
over national brands, banks or anything that is really a directory or publisher. To change them:
`rivals.py <run> --rivals a.com,b.com,c.com`. Tell the user which three and why, in one line.

**4. The results page and the ranking pages (MCP, up to 5 calls).** rivals.py prints these:
- A. `serp_organic_live_advanced` for the primary keyword at the serp location, depth 20.
- B. `dataforseo_labs_google_ranked_keywords` limit 1, filtered to the primary keyword, once for the
  site and once per rival: the `url` and `rank_group` each one ranks with.

Write `<run>/serp.json`:
```json
{"features": ["local_pack", "people_also_ask"],
 "ai_overview_refs": ["domain.com"],
 "local_pack": [{"title": "Business name", "city": "Columbia, SC", "rating": 5.0, "reviews": 295}],
 "site_pages": {"example.com": {"url": "https://example.com/", "position": 12},
                "rival.com": {"url": "https://rival.com/locations/x", "position": 7}},
 "brands": {"rival.com": "Rival Business Name"},
 "organic": [{"position": 1, "url": "", "breadcrumb": "https://www.site.com/path",
              "website_name": "Site", "title": "Page title"}]}
```
- `organic`: every organic item, `position` = rank_group. Google wraps URLs in long google.com/goto
  links. You can leave `url` empty and give `breadcrumb` as a plain URL (domain plus the path shown,
  "›" turned into "/"); prepare.py uses whichever resolves.
- `site_pages`: from the B calls. Leave a site out if it has no result (its homepage is used).
- `brands`: each rival's business name as searchers would type it.

**5. Prepare (free).** `python3 "$SKILL_DIR/scripts/prepare.py" <run>`. It prints the pages being
compared, a first guess at each page-one result's page type, and the exact MCP calls to make. It
writes an `mcp.json` skeleton.

**6. Collect (MCP, about 25 calls).** Make the calls prepare.py printed; independent ones in parallel.
Fill `<run>/mcp.json`:
- `page_types`: correct the guesses using the titles. Allowed: homepage, location page, service page,
  directory listing, list article, article, tool / rates, forum / social, video, other.
  A "best X in Y" roundup is a list article; a searchable list of businesses is a directory listing.
- `sites[<root>]`: one flat object per site with the fields named in the printed list.
- `gbp`: the Business Profile attached to each website. `extra_categories` = number of additional
  categories, `services` = number of services listed, `photos` = total_photos. For a brand with many
  branches, use the branch nearest the user's market or leave it null and say so.
- `link_gap`, `chatgpt`, and `calls` (total MCP calls this run).
Leave null whatever fails (Lighthouse often times out: retry once, then move on) and mention it.

**7. Teardown (free).** `python3 "$SKILL_DIR/scripts/teardown.py" <run>`

**8. Score.** `python3 "$SKILL_DIR/scripts/report.py" <run>` writes scores.json, report.html, artifact.html.

**9. Plan.** Read `scores.json` and `teardown.json`, then write `<run>/plan.json` (schema below).

**10. Package.** Rerun step 8, then `python3 "$SKILL_DIR/scripts/export.py" <run>`.

**11. Show it.**
- **Artifact tool available** (Claude desktop Code tab, claude.ai/code): publish `<run>/artifact.html`
  as it is with the Artifact tool: `icon` "chart", `description` = the headline. Do not edit or
  restyle it. Give the user the link. On a rerun in the same conversation publish the same path.
- **No Artifact tool:** `python3 "$SKILL_DIR/scripts/open_report.py" <run>`.

Do NOT rebuild, restyle or summarise the report as your own HTML or markdown page. The template is
the design; your job is the judgment in plan.json.

## plan.json
```json
{"headline": "short verdict, max 12 words",
 "dek": "two sentences: who is ahead and on what, and where the site leads",
 "rival_note": "why these three; which are the realistic benchmark; what the keyword grid shows",
 "intent_note": "what the page types on page one mean for this site",
 "moves": [{"tag": "week|time|keep|dont", "title": "...", "body": "...", "evidence": "the numbers",
            "steps": ["3 to 4 concrete actions"], "done_when": "...",
            "watch": "<a row label copied exactly from scores.json>", "baseline": "today's value"}]}
```
How to read the data before writing:
- **Keyword grid first.** Where is the site behind, and what do those keywords have in common (a word
  it does not use, a service, a city)? Where is it already ahead?
- **status** in scores.json: `all` = every rival is ahead (strongest evidence, build moves on these),
  `most` = worth a look, `lead` = the site beats every rival (rule it out, say so), `thin` = only one
  rival had data (do not lean on it), `even`/`some` = no pattern.
- **Page types.** If page one is mostly directories and list articles, the route is getting listed and
  the map pack, not out-optimising a homepage. If it is location or service pages and the site ranks
  with a homepage, the missing page is the move.
- **Map pack.** Compare reviews and categories with the rivals and with the businesses in the pack.
- A national brand among the rivals explains itself by scale. Benchmark targets on the like-for-like
  rivals and say so in a "dont" move.

Rules: 4 to 6 moves, ordered by impact. Every number checked against the JSON. No em dashes. Include a
"keep" move for something the site leads on and a "dont" move for something not worth copying. If the
gaps are small, say they are small.

## Finish (chat message)
4 to 6 lines: the artifact link, the three rivals and how often each is ahead, the headline, the two
or three gaps all rivals share with their numbers, what was ruled out, the package folder path, and:
"Drag the package folder into Claude or ChatGPT and say: work through ACTION_PLAN.md one step at a
time." Say how many DataForSEO calls were made and what could not be collected.

## Known data quirks
- Keyword positions come from DataForSEO Labs (stored national results). The live results page for one
  location can look quite different. Use Labs positions to pick rivals, the live page for page types
  and the map pack.
- The MCP SERP usually returns page one only (about 9 or 10 organic results).
- `backlinks_bulk_pages_summary` omits fields for pages with no links: treat as 0.
- `business_listings_search` returns branches and individual staff listings too: take the listing with
  the most reviews for each domain. A main listing can be missing; search by `title` if so.
- `backlinks_domain_intersection` with several targets returns sites linking to all of them. Most are
  spam; keep the recognisable ones and record the spam score.
- llm_mentions `mentions` = Google AI answers mentioning the domain. Never compare one site's total with
  another's co-citation count.
- The MCP Lighthouse runs a desktop profile and fails on some sites.
