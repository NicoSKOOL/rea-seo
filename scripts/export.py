"""REA SEO, step 4: build the take-away package for a run.

Usage: python scripts/export.py runs/<slug>
Writes runs/<slug>/package/ (and a zip next to it):
  report.html        the visual report
  ACTION_PLAN.md     the plan as a checklist: steps, evidence, done-when, metric + baseline
  README.md          what is in the folder and how to use it inside a project
  data/scores.csv    every head-to-head row
  data/top10.csv     page one
  data/link_gap.csv  sites linking to the #1 but not to you (with outreach columns)
  data/baseline.json key numbers today, for a re-check later
  data/raw/          collected.json, teardown.json, plan.json
"""
import csv, json, os, shutil, sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from report import fmt, g, LEAD_TXT, relabel  # noqa: E402

TAG = {"week": "Do this week", "time": "Takes time", "dont": "Don't copy", "keep": "Keep doing"}


def main(run):
    run = run.rstrip("/")
    col = json.load(open(f"{run}/collected.json"))
    td = json.load(open(f"{run}/teardown.json"))
    scores = json.load(open(f"{run}/scores.json"))
    plan = json.load(open(f"{run}/plan.json")) if os.path.exists(f"{run}/plan.json") else {}
    R, Y = td["sites"]["rival"], td["sites"]["you"]
    pkg = f"{run}/package"
    shutil.rmtree(pkg, ignore_errors=True)
    os.makedirs(f"{pkg}/data/raw")
    shutil.copy(f"{run}/report.html", pkg)
    for f in ("collected.json", "teardown.json", "plan.json"):
        if os.path.exists(f"{run}/{f}"):
            shutil.copy(f"{run}/{f}", f"{pkg}/data/raw")

    with open(f"{pkg}/data/scores.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["area", "check", relabel(R["root"] + " (#1)", R), Y["root"] + " (you)", "who leads"])
        for a in scores:
            for r in a["rows"]:
                w.writerow([a["name"], r["label"], fmt(r["rival"], r["kind"]), fmt(r["you"], r["kind"]), relabel(LEAD_TXT[r["lead"]], R)])

    with open(f"{pkg}/data/top10.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["position", "domain", "url", "title", "site referring domains", "page referring domains",
                    "mobile speed score", "words"])
        for r in sorted([x for x in col["results"] if x.get("position")], key=lambda x: x["position"]):
            w.writerow([r["position"], r["root"], r["url"], r.get("title"), g(r, "site", "referring_domains"),
                        g(r, "links", "referring_domains"), g(r, "lighthouse", "performance"), g(r, "content", "word_count")])

    gap = td.get("link_gap") or {}
    with open(f"{pkg}/data/link_gap.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["domain", "domain rank", relabel("links to the #1", R), "first seen", "pitched on", "reply", "notes"])
        for i in gap.get("items", []):
            w.writerow([i.get("domain"), i.get("rank"), i.get("backlinks"), i.get("first_seen"), "", "", ""])

    baseline = {"keyword": col["keyword"], "date": date.today().isoformat(), "you": Y["root"], "rival": R["root"],
                "position_you": Y.get("position"), "position_rival": R.get("position"),
                "areas": {a["name"]: {"lead": a["lead"], "rival_wins": a["rival_wins"], "you_wins": a["you_wins"]} for a in scores},
                "metrics": {r["label"]: {"rival": r["rival"], "you": r["you"]} for a in scores for r in a["rows"]},
                "link_gap_total": gap.get("total")}
    json.dump(baseline, open(f"{pkg}/data/baseline.json", "w"), indent=1, ensure_ascii=False, default=str)

    L = [f"# Action plan: take #1 for \"{col['keyword']}\"", "",
         f"- You: {Y['root']} (position {Y.get('position')})",
         f"- The #1: {R['root']}",
         f"- Run date: {date.today():%d %b %Y}", "",
         f"**{plan.get('headline', '')}**", "", plan.get("dek", ""), "",
         "Tick steps off as you go. Rerun REA SEO in 30 days and compare against `data/baseline.json`.", "",
         "## Scoreboard", ""]
    for a in scores:
        L.append(f"- {a['name']}: {LEAD_TXT[a['lead']] if a['lead'] != 'tie' else 'Even'} ({a['rival_wins']} vs {a['you_wins']})")
    L += ["", "## The moves", ""]
    for n, m in enumerate(plan.get("moves") or [], 1):
        L += [f"### {n}. {m['title']}", "", f"`{TAG.get(m.get('tag'), '')}`", "", m["body"], ""]
        for s in m.get("steps") or []:
            L.append(f"- [ ] {s}")
        L.append("")
        if m.get("evidence"):
            L.append(f"- Evidence: {m['evidence']}")
        if m.get("done_when"):
            L.append(f"- Done when: {m['done_when']}")
        if m.get("watch"):
            L.append(f"- Number to watch: {m['watch']} (today: {m.get('baseline', 'see baseline.json')})")
        L.append("")
    L += ["## What this can't see", "",
          "- Google's click and engagement data.", "- Google Business Profile, reviews and offline brand strength.",
          "- The full internal link graph (page and homepage only).",
          "- Link and traffic numbers are DataForSEO estimates, not Google's index.", "",
          "Every finding is a difference between two sites, not proof of why Google ranks one higher."]
    open(f"{pkg}/ACTION_PLAN.md", "w").write(relabel("\n".join(L) + "\n", R))

    open(f"{pkg}/README.md", "w").write(f"""# REA SEO package: "{col['keyword']}"

{Y['root']} against the #1 result, {R['root']}. Run on {date.today():%d %b %Y}.

## What's here
- `report.html`: the visual report. Open it in a browser.
- `ACTION_PLAN.md`: the plan as a checklist, with steps, evidence, a done-when line and a number to watch per move.
- `data/scores.csv`: every head-to-head check.
- `data/top10.csv`: page one of Google for the keyword.
- `data/link_gap.csv`: sites linking to the #1 but not to you, with columns to log outreach.
- `data/baseline.json`: today's numbers, for comparing after a rerun.
- `data/raw/`: the full data behind the report.

## Use it in a project
Drop this folder into your site's project (for example `seo/rea-seo/`). Then ask Claude or Codex:

> Read seo/rea-seo/ACTION_PLAN.md and the files in seo/rea-seo/data. Do move 1, step by step, and tick each step off in ACTION_PLAN.md as it is finished. Don't change anything listed under a "Don't copy" move.

## Check progress
Rerun REA SEO on the same keyword in 30 days and compare the new numbers with `data/baseline.json`.

Inspired by REA (github.com/morluto/rea), not affiliated.
""")
    readme = f"{pkg}/README.md"
    open(readme, "w").write(relabel(open(readme).read(), R))
    zip_path = shutil.make_archive(f"{run}/rea-seo-{os.path.basename(run)}", "zip", pkg)
    print(f"-> {pkg}/\n-> {zip_path}")


if __name__ == "__main__":
    main(sys.argv[1])
