"""REA SEO step 10: build the take-away package for a run.

Usage: python3 export.py rea-seo/<slug>
Writes <run>/package/ (and a zip next to it):
  report.html          the visual report
  ACTION_PLAN.md       the plan as a checklist: steps, evidence, done-when, number to watch
  README.md            what is in the folder and how to use it inside a project
  data/keywords.csv    positions for every keyword, you and each rival
  data/scores.csv      every check, you and each rival
  data/page_one.csv    the live results page with page types
  data/gbp.csv         Google Business Profile comparison
  data/link_gap.csv    sites linking to all rivals but not to you
  data/baseline.json   today's numbers, for a re-check later
  data/raw/            teardown.json, scores.json, plan.json
"""
import csv, json, os, shutil, sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from report import fmt, chip_text, LETTERS  # noqa: E402

TAG = {"week": "Do this week", "time": "Takes time", "dont": "Don't copy", "keep": "Keep doing"}


def wcsv(path, head, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(head)
        w.writerows(rows)


def main(run):
    run = run.rstrip("/\\")
    ld = lambda f: json.load(open(f"{run}/{f}", encoding="utf-8"))  # noqa: E731
    td, scores = ld("teardown.json"), ld("scores.json")
    plan = ld("plan.json") if os.path.exists(f"{run}/plan.json") else {}
    you, rivals = td["sites"][0], td["sites"][1:]
    names = [f"{LETTERS[i]} {r['root']}" for i, r in enumerate(rivals)]
    pkg = f"{run}/package"
    shutil.rmtree(pkg, ignore_errors=True)
    os.makedirs(f"{pkg}/data/raw")
    shutil.copy(f"{run}/report.html", pkg)
    for f in ("teardown.json", "scores.json", "plan.json"):
        if os.path.exists(f"{run}/{f}"):
            shutil.copy(f"{run}/{f}", f"{pkg}/data/raw")

    mx = td["matrix"]
    wcsv(f"{pkg}/data/keywords.csv", ["keyword", "monthly searches", you["root"] + " (you)"] + names,
         [[k["keyword"], k.get("volume"), mx["you"][i]] + [r["positions"][i] for r in mx["rivals"]]
          for i, k in enumerate(mx["keywords"])])
    wcsv(f"{pkg}/data/scores.csv", ["area", "check", you["root"] + " (you)"] + names + ["result"],
         [[a["name"], r["label"], fmt(r["you"], r["kind"])] + [fmt(v, r["kind"]) for v in r["rivals"]]
          + [chip_text(r["status"], r["ahead"], r["compared"])] for a in scores for r in a["rows"]])
    wcsv(f"{pkg}/data/page_one.csv", ["position", "domain", "page type", "title", "url"],
         [[x["position"], x["root"], x["page_type"], x.get("title"), x["url"]] for x in td["serp"]["rows"]])
    wcsv(f"{pkg}/data/gbp.csv", ["site", "profile", "city", "category", "rating", "reviews", "photos", "services", "in map pack"],
         [[s["root"]] + [(s.get("gbp") or {}).get(k) for k in ("name", "city", "category", "rating", "reviews", "photos", "services", "in_pack")]
          for s in td["sites"]])
    gap = td.get("link_gap") or {}
    wcsv(f"{pkg}/data/link_gap.csv", ["domain", "spam score", "pitched on", "reply", "notes"],
         [[i.get("domain"), i.get("spam"), "", "", ""] for i in gap.get("items", [])])

    json.dump({"site": you["root"], "date": date.today().isoformat(), "primary_keyword": td["keyword"],
               "rivals": [r["root"] for r in rivals],
               "positions": {k["keyword"]: {"you": mx["you"][i], **{r["root"]: r["positions"][i] for r in mx["rivals"]}}
                             for i, k in enumerate(mx["keywords"])},
               "checks": {r["label"]: {"you": r["you"], "rivals": r["rivals"], "status": r["status"]}
                          for a in scores for r in a["rows"]}},
              open(f"{pkg}/data/baseline.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)

    L = [f"# Action plan: {you['root']}", "",
         f"- Compared with: {', '.join(names)}",
         f"- Keywords checked: {len(mx['keywords'])} (main: \"{td['keyword']}\")",
         f"- Run date: {date.today():%d %b %Y}", "",
         f"**{plan.get('headline', '')}**", "", plan.get("dek", ""), "",
         "Tick steps off as you go. Rerun REA SEO in 30 days and compare against `data/baseline.json`.", ""]
    for title, st in (("All rivals are ahead (start here)", "all"), ("Most rivals are ahead", "most"),
                      ("You lead all of them (not the gap)", "lead")):
        L += [f"## {title}", ""]
        rows = [r for a in scores for r in a["rows"] if r["status"] == st]
        L += [f"- {r['label']}: you {fmt(r['you'], r['kind'])}; "
              + ", ".join(f"{LETTERS[i]} {fmt(v, r['kind'])}" for i, v in enumerate(r["rivals"])) for r in rows] or ["- none"]
        L.append("")
    L += ["## The moves", ""]
    for n, m in enumerate(plan.get("moves") or [], 1):
        L += [f"### {n}. {m['title']}", "", f"`{TAG.get(m.get('tag'), '')}`", "", m["body"], ""]
        L += [f"- [ ] {s}" for s in m.get("steps") or []] + [""]
        if m.get("evidence"):
            L.append(f"- Evidence: {m['evidence']}")
        if m.get("done_when"):
            L.append(f"- Done when: {m['done_when']}")
        if m.get("watch"):
            L.append(f"- Number to watch: {m['watch']} (today: {m.get('baseline', 'see baseline.json')})")
        L.append("")
    L += ["## What this can't see", "",
          "- Google's click and engagement data.", "- How far each business is from the searcher (map pack).",
          "- The full internal link graph (ranking page and homepage only).",
          "- Positions, links and traffic are DataForSEO estimates, not Google's index.", "",
          "Every finding is a difference between sites, not proof of why Google ranks one higher."]
    open(f"{pkg}/ACTION_PLAN.md", "w", encoding="utf-8").write("\n".join(L) + "\n")

    open(f"{pkg}/README.md", "w", encoding="utf-8").write(f"""# REA SEO package: {you['root']}

{you['root']} against {', '.join(r['root'] for r in rivals)}, across {len(mx['keywords'])} keywords. Run on {date.today():%d %b %Y}.

## What's here
- `report.html`: the visual report. Open it in a browser.
- `ACTION_PLAN.md`: the gaps and the plan as a checklist.
- `data/keywords.csv`: positions for every keyword, you and each rival.
- `data/scores.csv`: every check, you and each rival.
- `data/page_one.csv`: the live results page for the main keyword, with page types.
- `data/gbp.csv`: Google Business Profile comparison.
- `data/link_gap.csv`: sites linking to all rivals but not to you, with columns to log outreach.
- `data/baseline.json`: today's numbers, for comparing after a rerun.
- `data/raw/`: the full data behind the report.

## Use it in a project
Drop this folder into your site's project (for example `seo/rea-seo/`). Then ask Claude or Codex:

> Read seo/rea-seo/ACTION_PLAN.md and the files in seo/rea-seo/data. Do move 1, step by step, and tick each step off in ACTION_PLAN.md as it is finished. Don't change anything listed under a "Don't copy" move.

Inspired by REA (github.com/morluto/rea), not affiliated.
""")
    zip_path = shutil.make_archive(f"{run}/rea-seo-{os.path.basename(run)}", "zip", pkg)
    print(f"-> {pkg}/\n-> {zip_path}")


if __name__ == "__main__":
    main(sys.argv[1])
