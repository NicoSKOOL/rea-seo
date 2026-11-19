"""REA SEO step 3: find who really outranks the site across the keyword set. Free.

Usage: python3 rivals.py rea-seo/<slug> [--rivals a.com,b.com,c.com]

Reads competitors.json, written by Claude from dataforseo_labs_google_serp_competitors:
  {"positions": {"domain.com": [12, 13, null, ...]}}   one position per keyword, in run.json order,
                                                        null where the domain does not rank
Writes rivals.json and prints the leaderboard plus the next MCP calls.
"""
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import root, kind_of, load, save  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("run")
ap.add_argument("--rivals", help="comma-separated domains to use instead of the automatic top 3")
a = ap.parse_args()
run = a.run.rstrip("/\\")
cfg, comp = load(f"{run}/run.json"), load(f"{run}/competitors.json")
if not cfg or not comp:
    sys.exit("Missing run.json or competitors.json in " + run)
kws = [k["keyword"] for k in cfg["keywords"]]
n = len(kws)

merged = {}  # root -> best position per keyword (subdomains folded in)
for dom, pos in comp["positions"].items():
    r = root(dom)
    pos = (list(pos) + [None] * n)[:n]
    cur = merged.setdefault(r, [None] * n)
    merged[r] = [min(x for x in (c, p) if x is not None) if (c is not None or p is not None) else None
                 for c, p in zip(cur, pos)]

site = cfg["site"]
you = merged.get(site, [None] * n)
rows = []
for r, pos in merged.items():
    if r == site:
        continue
    ranked = [p for p in pos if p is not None]
    beats = sum(1 for p, y in zip(pos, you) if p is not None and (y is None or p < y))
    rows.append({"root": r, "kind": kind_of(r), "beats": beats, "ranked": len(ranked),
                 "avg": round(sum(ranked) / len(ranked), 1) if ranked else None, "positions": pos})
rows.sort(key=lambda x: (-x["beats"], x["avg"] or 999))

if a.rivals:
    picks = [root(x.strip()) for x in a.rivals.split(",") if x.strip()]
    missing = [p for p in picks if p not in merged]
    for p in missing:
        rows.append({"root": p, "kind": kind_of(p), "beats": 0, "ranked": 0, "avg": None, "positions": [None] * n})
else:
    picks = [x["root"] for x in rows if x["kind"] == "web" and x["beats"] > 0][:3]
if not picks:
    sys.exit("No business site outranks this site on these keywords. Pick wider keywords or pass --rivals.")

by = {x["root"]: x for x in rows}
save(f"{run}/rivals.json", {
    "keywords": cfg["keywords"], "you": {"root": site, "positions": you},
    "rivals": [by[p] for p in picks],
    "others": [x for x in rows if x["root"] not in picks and x["beats"] > 0][:10]})

print(f"\nKeywords: {n}.  {site} ranks for {sum(p is not None for p in you)} of them.\n")
print(f'{"":2}{"domain":36}{"kind":13}{"ahead of you":>13}{"avg pos":>9}')
for x in rows[:18]:
    mark = "*" if x["root"] in picks else " "
    print(f'{mark:2}{x["root"]:36}{x["kind"]:13}{str(x["beats"]) + " of " + str(n):>13}{str(x["avg"]):>9}')
print("\n* = rivals for the teardown. To change them, rerun with --rivals a.com,b.com,c.com")
print("  Pick the site ahead most often, then like-for-like businesses (same kind of company and market).")
P = cfg["primary"]
print(f"""
Next MCP calls:
 A serp_organic_live_advanced  keyword="{P}" location_name="{cfg['serp_location']}" language_code="{cfg['language_code']}" depth=20
 B dataforseo_labs_google_ranked_keywords, once per site below, limit=1,
   filters=[["keyword_data.keyword","=","{P}"]]  -> the page each site ranks with (url + rank_group)
   targets: {[site] + picks}
Then write {run}/serp.json (see SKILL.md) and run prepare.py.""")
