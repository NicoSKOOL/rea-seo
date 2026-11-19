"""REA SEO step 8: score teardown.json and render report.html + artifact.html.

Usage: python3 report.py rea-seo/<slug>
Reads teardown.json (+ plan.json written by Claude, optional). Writes scores.json, report.html
(self-contained, for the package) and artifact.html (the same page as a fragment for the Artifact tool).

Rule: every row is a difference between sites, never a cause.
"""
import html, json, math, os, re, sys
from datetime import date

E = lambda x: html.escape(str(x))  # noqa: E731
LETTERS = "ABC"


def g(d, *path):
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d


def bots_allowed(s):
    b = g(s, "agentic", "robots", "bots") or {}
    return sum(v.startswith("allowed") for v in b.values()) if b else None


def domain_age(s):
    c = g(s, "site_metrics", "created")
    if not c:
        return None
    y, m, d = map(int, c[:10].split("-"))
    return round((date.today() - date(y, m, d)).days / 365.25, 1)


def title_ok(s):
    o = s["onpage"]
    if o.get("error"):
        return None
    return bool(o.get("title_has_terms")) and 30 <= (o.get("title_len") or 0) <= 65


def op(key):
    return lambda s: None if g(s, "onpage", "error") else g(s, "onpage", key)


def alt_share(s):
    n = g(s, "onpage", "images")
    return (g(s, "onpage", "images_with_alt") or 0) / n if n else None


def categories(s):
    return None if g(s, "gbp", "category") is None or g(s, "gbp", "extra_categories") is None \
        else 1 + g(s, "gbp", "extra_categories")


# (key, label, getter, better: "high" | "low" | "yes" | None (context only), format)
AREAS = [
    ("gbp", "Google Business Profile", "What Google shows in the map pack", [
        ("reviews", "Google reviews", lambda s: g(s, "gbp", "reviews"), "high", "num"),
        ("rating", "Google rating", lambda s: g(s, "gbp", "rating"), "high", "r1"),
        ("cats", "Business categories", categories, "high", "num"),
        ("photos", "Photos on the profile", lambda s: g(s, "gbp", "photos"), "high", "num"),
        ("services", "Services listed", lambda s: g(s, "gbp", "services"), "high", "num"),
        ("pack", "In the map pack for the main keyword", lambda s: g(s, "gbp", "in_pack"), "yes", "bool"),
    ]),
    ("backlinks", "Authority & brand", "Who vouches for the site, and who searches for it", [
        ("rd", "Referring domains (site)", lambda s: g(s, "backlinks", "referring_domains"), "high", "num"),
        ("rank", "Domain rank (DataForSEO, 0 to 1000)", lambda s: g(s, "backlinks", "rank"), "high", "num"),
        ("page_rd", "Referring domains (ranking page)", lambda s: g(s, "backlinks", "page_referring_domains"), "high", "num"),
        ("brand", "Brand-name searches / month", lambda s: g(s, "site_metrics", "brand_volume"), "high", "num"),
        ("age", "Domain age (years)", domain_age, "high", "num"),
        ("dofollow", "Dofollow share", lambda s: g(s, "backlinks", "dofollow_share"), "high", "pct"),
        ("spam", "Backlink spam score", lambda s: g(s, "backlinks", "spam_score"), "low", "num"),
        ("etv", "Estimated organic visits / month", lambda s: g(s, "site_metrics", "etv"), None, "num"),
    ]),
    ("onpage", "On-page SEO", "What Google reads in the HTML of the ranking page", [
        ("title", "Title uses the keyword, 30 to 65 chars", title_ok, "yes", "bool"),
        ("meta", "Meta description length", op("meta_description_len"), "high", "chars"),
        ("canon", "Self-referencing canonical", op("canonical_self"), "yes", "bool"),
        ("h1", "Exactly one H1", lambda s: None if g(s, "onpage", "error") else g(s, "onpage", "h1_count") == 1, "yes", "bool"),
        ("schema", "Schema types on the page", lambda s: None if g(s, "onpage", "error") else len(g(s, "onpage", "schema_types") or []), "high", "num"),
        ("faq", "FAQ schema", op("has_faq_schema"), "yes", "bool"),
        ("alt", "Images with alt text", alt_share, "high", "pct"),
    ]),
    ("content", "Content", "What the ranking page says", [
        ("words", "Words in the HTML", op("raw_words"), None, "num"),
        ("headings", "Headings (H1 to H4)", lambda s: None if g(s, "onpage", "error") else len(g(s, "onpage", "headings") or []), "high", "num"),
        ("mentions", "Keyword terms in the text", op("term_mentions"), "high", "num"),
        ("internal", "Internal links on the page", op("internal_unique"), "high", "num"),
    ]),
    ("structure", "Pages & structure", "How the site is organised", [
        ("urls", "Pages in the sitemap", lambda s: g(s, "structure", "sitemap_urls") or None, "high", "num"),
        ("depth", "Clicks deep (URL folders)", lambda s: g(s, "structure", "page_depth"), None, "num"),
        ("home", "Linked from the homepage", lambda s: g(s, "structure", "page_linked_from_home"), "yes", "bool"),
    ]),
    ("agentic", "Agentic SEO / GEO", "Can AI crawlers and answer engines use it", [
        ("bots", "AI crawlers allowed (of 9)", bots_allowed, "high", "num"),
        ("llms", "llms.txt file", lambda s: g(s, "agentic", "llms_txt", "found"), "yes", "bool"),
        ("aio", "Mentions in Google AI answers", lambda s: g(s, "agentic", "llm_mentions"), "high", "num"),
        ("gpt", "Named in ChatGPT's answer", lambda s: s.get("_gpt"), "yes", "bool"),
    ]),
    ("speed", "Speed", "Lighthouse lab test of the ranking page", [
        ("perf", "Performance score", lambda s: g(s, "speed", "performance"), "high", "num"),
        ("lcp", "Largest paint", lambda s: g(s, "speed", "lcp_ms"), "low", "ms"),
        ("cls", "Layout shift", lambda s: g(s, "speed", "cls"), "low", "cls"),
    ]),
]


def fmt(v, kind):
    if v is None:
        return "n/a"
    if kind == "bool":
        return "Yes" if v else "No"
    if kind == "pct":
        return f"{v * 100:.0f}%"
    if kind == "ms":
        return f"{v / 1000:.1f}s"
    if kind == "cls":
        return f"{v:.2f}"
    if kind == "r1":
        return f"{v:.1f}"
    if kind == "chars":
        return f"{v} ch"
    v = float(v)
    if v >= 1e6:
        return f"{v / 1e6:.1f}M"
    if v >= 10000:
        return f"{v / 1000:.0f}K"
    if v >= 1000:
        return f"{v / 1000:.1f}K".replace(".0K", "K")
    return f"{v:.1f}" if v < 10 and v != int(v) else f"{v:,.0f}"


def status(you, rivals, better):
    """all = every rival is ahead, most = more than half, some, lead = you beat all, even,
    thin = too few rivals had data to say. Numbers within 5% of each other count as level."""
    if better is None or you is None:
        return "ctx", 0, 0
    vals = [r for r in rivals if r is not None]
    if not vals:
        return "ctx", 0, 0

    def ahead(a, b):  # is a clearly better than b
        if better == "yes":
            return bool(a) and not bool(b)
        if abs(a - b) <= 0.05 * max(abs(a), abs(b)):
            return False
        return a > b if better == "high" else a < b
    b = sum(ahead(r, you) for r in vals)
    w = sum(ahead(you, r) for r in vals)
    n = len(vals)
    if n < 2 and len(rivals) > 1:
        return "thin", b, n
    if b == n:
        return "all", b, n
    if b * 2 > n:
        return "most", b, n
    if w == n:
        return "lead", b, n
    return ("some" if b else "even"), b, n


def chip_text(st, b, n):
    return {"all": f"All {n} ahead", "most": f"{b} of {n} ahead", "some": f"{b} of {n} ahead",
            "lead": "You lead", "even": "Even", "ctx": "Context", "thin": f"{n} rival checked"}[st]


def score(td):
    gpt = (td.get("chatgpt") or {}).get("mentioned") or {}
    for s in td["sites"]:
        s["_gpt"] = gpt.get(s["root"])
    you, rivals = td["sites"][0], td["sites"][1:]
    out = []
    for key, name, sub, rows in AREAS:
        res = []
        for k, label, fn, better, kind in rows:
            def val(s):
                try:
                    return fn(s)
                except Exception:  # noqa: BLE001
                    return None
            y, rs = val(you), [val(r) for r in rivals]
            st, b, n = status(y, rs, better)
            res.append({"key": k, "label": label, "you": y, "rivals": rs, "kind": kind, "better": better,
                        "status": st, "ahead": b, "compared": n})
        out.append({"key": key, "name": name, "sub": sub, "rows": res,
                    "gaps": sum(r["status"] in ("all", "most") for r in res),
                    "leads": sum(r["status"] == "lead" for r in res)})
    return out


# ---------- rendering ----------

def row_vals(r):
    return " · ".join([f'You {fmt(r["you"], r["kind"])}'] +
                      [f'{LETTERS[i]} {fmt(v, r["kind"])}' for i, v in enumerate(r["rivals"])])


def area_html(a, n):
    rows = []
    for r in a["rows"]:
        cells = f'<div class="val v-y">{E(fmt(r["you"], r["kind"]))}</div>'
        for v in r["rivals"]:
            win = r["better"] and r["you"] is not None and v is not None and \
                status(r["you"], [v], r["better"])[1] == 1
            cells += f'<div class="val{" v-r" if win else ""}">{E(fmt(v, r["kind"]))}</div>'
        rows.append(f'<div class="row st-{r["status"]}"><div class="lab">{E(r["label"])}</div>{cells}'
                    f'<div class="chip c-{r["status"]}">{chip_text(r["status"], r["ahead"], r["compared"])}</div></div>')
    heads = '<div class="val v-y">You</div>' + "".join(f'<div class="val">{LETTERS[i]}</div>' for i in range(n))
    return f'''<section class="area" id="{a["key"]}">
 <header><div><h3>{E(a["name"])}</h3><p>{E(a["sub"])}</p></div>
 <div class="tally"><span class="t-r">{a["gaps"]}</span> gaps <em>/</em> <span class="t-y">{a["leads"]}</span> leads</div></header>
 <div class="scroll"><div class="tbl" style="--n:{n + 1}">
 <div class="row head"><div></div>{heads}<div></div></div>{"".join(rows)}</div></div>
</section>'''


def render(run):
    run = run.rstrip("/\\")
    td = json.load(open(os.path.join(run, "teardown.json"), encoding="utf-8"))
    plan_p = os.path.join(run, "plan.json")
    plan = json.load(open(plan_p, encoding="utf-8")) if os.path.exists(plan_p) else {}
    areas = score(td)
    json.dump(areas, open(os.path.join(run, "scores.json"), "w", encoding="utf-8"), indent=1,
              ensure_ascii=False, default=str)
    you, rivals = td["sites"][0], td["sites"][1:]
    n = len(rivals)
    mx = td["matrix"]
    kws = mx["keywords"]
    nk = len(kws)
    allrows = [r for a in areas for r in a["rows"]]
    by = lambda st: [r for r in allrows if r["status"] == st]  # noqa: E731

    # hero tiles
    ypos = mx["you"]
    top10 = sum(1 for p in ypos if p is not None and p <= 10)
    main = mx["rivals"][0]
    tiles = [(str(nk), "keywords checked"), (f"{top10} of {nk}", "you rank in the top 10"),
             (f'{main["beats"]} of {nk}', f'{main["root"]} is ahead of you'),
             (str(len(by("all"))), f"checks where all {n} rivals are ahead"),
             (str(len(by("lead"))), f"checks where you lead all {n}")]
    tiles_html = "".join(f'<div class="tile"><b>{E(a)}</b><span>{E(b)}</span></div>' for a, b in tiles)

    # leaderboard + matrix
    leaders = ""
    for i, (r, s) in enumerate(zip(mx["rivals"], rivals)):
        leaders += (f'<div class="lead"><span class="badge">{LETTERS[i]}</span><div><h4>{E(s["brand"])}</h4>'
                    f'<div class="url">{E(r["root"])}</div></div>'
                    f'<div class="big">{r["beats"]}<small> of {nk}</small></div>'
                    f'<p>keywords ahead of you · average position {fmt(r["avg"], "num")} · '
                    f'{fmt(g(s, "site_metrics", "etv"), "num")} est. visits / month</p></div>')
    mrows = ""
    for i, k in enumerate(kws):
        yp = ypos[i]
        cells = f'<div class="val v-y{" top" if yp and yp <= 3 else ""}">{yp if yp else "–"}</div>'
        for r in mx["rivals"]:
            rp = r["positions"][i]
            ahead = rp is not None and (yp is None or rp < yp)
            cells += f'<div class="val{" ahead" if ahead else ""}">{rp if rp else "–"}</div>'
        prim = ' <i class="prim">main</i>' if k["keyword"] == td["keyword"] else ""
        mrows += (f'<div class="row"><div class="lab">{E(k["keyword"])}{prim}</div>'
                  f'<div class="val dim">{fmt(k.get("volume"), "num") if k.get("volume") else "–"}</div>{cells}</div>')
    mhead = ('<div class="row head"><div>Keyword</div><div class="val">Searches</div><div class="val v-y">You</div>'
             + "".join(f'<div class="val">{LETTERS[i]}</div>' for i in range(n)) + "</div>")
    others = "".join(f'<span>{E(o["root"])} <b>{o["beats"]}</b> <em>{E(o["kind"]).replace("web", "business")}</em></span>'
                     for o in mx.get("others") or [])

    # what Google shows
    rroots = {s["root"]: LETTERS[i] for i, s in enumerate(rivals)}
    srows = ""
    rows = td["serp"]["rows"]
    for x in rows:
        cls = "s-y" if x["root"] == you["root"] else ("s-r" if x["root"] in rroots else "")
        srows += (f'<li class="{cls}"><span class="pos">{x["position"]}</span>'
                  f'<span class="dom"><b>{E(x["root"])}</b><small>{E(x.get("title") or "")}</small></span>'
                  f'<span class="type">{E(x["page_type"])}</span></li>')
    tc = td["serp"]["type_counts"]
    tot = sum(c for _, c in tc) or 1
    tbars = "".join(f'<li><span>{E(t)}</span><i style="width:{c / tot * 100:.0f}%"></i><b>{c}</b></li>' for t, c in tc)
    biz = sum(1 for x in rows if x["kind"] == "web" and x["page_type"] in ("homepage", "location page", "service page"))
    top_t, top_c = (tc[0] if tc else ("", 0))
    facts = (f'{top_c} of {len(rows)} page-one results are {top_t}s. '
             f'{biz} of {len(rows)} {"is a single business\'s" if biz == 1 else "are single businesses\'"} own page. '
             f'Your ranking page is a {you.get("page_type") or "page"}'
             + "".join(f'; {LETTERS[i]} ranks with a {s.get("page_type") or "page"}' for i, s in enumerate(rivals)) + ".")
    feats = "".join(f"<span>{E(f.replace('_', ' '))}</span>" for f in td["serp"]["features"]) or "<span>none</span>"

    # map pack + GBP
    names = {(g(s, "gbp", "name") or s["brand"] or "").lower(): ("You" if i == 0 else LETTERS[i - 1])
             for i, s in enumerate(td["sites"])}
    pack = ""
    for i, p in enumerate(td["serp"]["local_pack"], 1):
        t = (p.get("title") or "").lower()
        who = next((v for k, v in names.items() if k and (k in t or t in k)), "")
        pack += (f'<li class="{"s-y" if who == "You" else ("s-r" if who else "")}"><span class="pos">{i}</span>'
                 f'<span class="dom"><b>{E(p.get("title"))}</b><small>{E(p.get("city") or "")}</small></span>'
                 f'<span class="m">{fmt(p.get("rating"), "r1")} ★ <em>{fmt(p.get("reviews"), "num")} reviews</em></span></li>')
    pack = pack or '<li><span class="dom"><small>No map pack on this results page.</small></span></li>'
    inpack = ["You" if i == 0 else LETTERS[i - 1] for i, s in enumerate(td["sites"]) if g(s, "gbp", "in_pack")]
    pack_fact = ("In this map pack: " + ", ".join(inpack) + ".") if inpack else (
        "Neither you nor any of the compared rivals is in this map pack." if td["serp"]["local_pack"] else "")
    gbp = ""
    for i, s in enumerate(td["sites"]):
        b = s.get("gbp") or {}
        tag = "You" if i == 0 else LETTERS[i - 1]
        if b.get("rating") is None and b.get("reviews") is None:
            body = '<p class="none">No profile data collected</p>'
        else:
            body = (f'<div class="stars">{fmt(b.get("rating"), "r1")}<small> ★</small></div>'
                    f'<div class="rev">{fmt(b.get("reviews"), "num")} reviews</div>'
                    f'<p>{E(b.get("category") or "")}{" · " + E(b["city"]) if b.get("city") else ""}</p>'
                    f'<p class="dim">{fmt(b.get("photos"), "num")} photos · {fmt(b.get("services"), "num")} services'
                    f'{" · in the map pack" if b.get("in_pack") else ""}</p>')
        gbp += (f'<div class="gcard {"gy" if i == 0 else ""}"><span class="badge">{tag}</span>'
                f'<h4>{E(b.get("name") or s["brand"])}</h4>{body}</div>')

    # evidence
    def ev(items, empty):
        return "".join(f'<li><b>{E(r["label"])}</b><span>{E(row_vals(r))}</span></li>' for r in items) or f"<li><span>{empty}</span></li>"

    # links + AI
    gap = td.get("link_gap") or {}
    gap_items = "".join(f'<li><span>{E(i["domain"])}</span><em>{("spam " + str(i["spam"])) if i.get("spam") else "clean"}</em></li>'
                        for i in gap.get("items", [])[:12]) or "<li><span>none found</span></li>"
    ment = [(("You" if i == 0 else LETTERS[i - 1]), s["root"], g(s, "agentic", "llm_mentions")) for i, s in enumerate(td["sites"])]
    mxm = max([m for _, _, m in ment if m] or [1])
    aio = "".join(f'<li class="{"s-y" if t == "You" else ""}"><span>{t} · {E(r)}</span>'
                  f'<i style="width:{max(1, math.sqrt((m or 0) / mxm) * 100):.0f}%"></i><b>{fmt(m, "num")}</b></li>' for t, r, m in ment)
    gp = td.get("chatgpt") or {}
    named = [("You" if i == 0 else LETTERS[i - 1]) for i, s in enumerate(td["sites"]) if (gp.get("mentioned") or {}).get(s["root"])]
    gpt_line = (f'ChatGPT\'s answer for "{td["keyword"]}" cited: ' + ", ".join(gp.get("sources", [])[:8]) + ". "
                + (f'Named in the answer: {", ".join(named)}.' if named else "None of the four sites was named.")) \
        if gp.get("sources") else "ChatGPT: not checked"

    # plan
    moves = plan.get("moves") or []
    TAG = {"week": "Do this week", "time": "Takes time", "dont": "Don't copy", "keep": "Keep doing"}

    def move(i, m):
        steps = "".join(f'<li><label><input type="checkbox" id="st-{i}-{j}" data-k="{i}-{j}"><span>{E(x)}</span></label></li>'
                        for j, x in enumerate(m.get("steps") or []))
        meta = ""
        if m.get("done_when"):
            meta += f'<div><b>Done when</b>{E(m["done_when"])}</div>'
        if m.get("watch"):
            meta += f'<div><b>Number to watch</b>{E(m["watch"])}: {E(m.get("baseline", ""))} today</div>'
        if m.get("evidence"):
            meta += f'<div><b>Evidence</b>{E(m["evidence"])}</div>'
        return f'''<li class="mv t-{E(m.get("tag", "week"))}"><span class="n">{i + 1:02d}</span>
 <div><span class="tag">{TAG.get(m.get("tag"), m.get("tag", ""))}</span><h4>{E(m["title"])}</h4><p>{E(m["body"])}</p>
 {f'<ul class="steps">{steps}</ul>' if steps else ""}{f'<div class="meta">{meta}</div>' if meta else ""}</div></li>'''
    moves_html = "".join(move(i, m) for i, m in enumerate(moves))

    calls = td.get("calls")
    rep = {
        "{{TITLE}}": E(f"Why {you['root']} is outranked"),
        "{{SITE}}": E(you["root"]), "{{BRAND}}": E(td.get("brand") or you["root"]),
        "{{KW}}": E(td["keyword"]), "{{LOC}}": E((td.get("serp_location") or td.get("location") or "").replace(",", ", ").replace(",  ", ", ")),
        "{{DATE}}": date.today().strftime("%d %b %Y"),
        "{{COST}}": f"DataForSEO MCP, {calls} calls" if calls else "DataForSEO MCP",
        "{{HEAD}}": E(plan.get("headline") or f"All {n} rivals are ahead on {len(by('all'))} checks. You lead on {len(by('lead'))}."),
        "{{DEK}}": E(plan.get("dek") or ""), "{{TILES}}": tiles_html,
        "{{NK}}": str(nk), "{{NR}}": str(n), "{{NCOL}}": str(n + 2),
        "{{LEADERS}}": leaders, "{{MHEAD}}": mhead, "{{MATRIX}}": mrows,
        "{{OTHERS}}": others or "<span>none</span>",
        "{{RIVAL_NOTE}}": E(plan.get("rival_note") or ""),
        "{{SERP_ROWS}}": srows, "{{TYPE_BARS}}": tbars, "{{FEATURES}}": feats, "{{FACTS}}": E(facts),
        "{{INTENT}}": E(plan.get("intent_note") or ""),
        "{{PACK}}": pack, "{{PACK_FACT}}": E(pack_fact), "{{GBP}}": gbp,
        "{{EV_ALL}}": ev(by("all"), "Nothing: no check has every rival ahead of you."),
        "{{EV_MOST}}": ev(by("most"), "Nothing here."),
        "{{EV_LEAD}}": ev(by("lead"), "Nothing here."),
        "{{N_ALL}}": str(len(by("all"))), "{{N_MOST}}": str(len(by("most"))), "{{N_LEAD}}": str(len(by("lead"))),
        "{{AREAS}}": "".join(area_html(a, n) for a in areas),
        "{{LEGEND}}": " ".join(f'<span><b>{LETTERS[i]}</b> {E(s["root"])}</span>' for i, s in enumerate(rivals)),
        "{{GAP_TOTAL}}": fmt(gap.get("total"), "num"), "{{GAP}}": gap_items,
        "{{AIO}}": aio, "{{GPT}}": E(gpt_line),
        "{{TOPICS}}": " ".join(f"<span>{E(t)}</span>" for t in (td.get("shared_topics") or [])[:24]) or "<span>none</span>",
        "{{NSTEPS}}": str(sum(len(m.get("steps") or []) for m in moves)),
        "{{SLUG}}": E(os.path.basename(run)),
        "{{MOVES}}": moves_html or '<li class="mv"><div><p>plan.json has not been written yet.</p></div></li>',
    }
    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "rea_report.html"),
               encoding="utf-8").read()
    for k, v in rep.items():
        tpl = tpl.replace(k, v)
    open(os.path.join(run, "report.html"), "w", encoding="utf-8").write(tpl)
    # artifact.html: same page as a fragment for Claude's Artifact tool (no wrapper tags, no local file links)
    art = re.sub(r"<!--FILES-->.*?<!--/FILES-->\n?", "", tpl, flags=re.S)
    art = re.sub(r"</?(?:html|head|body)[^>]*>\n?|<!doctype html>\n?|<meta (?:charset|name=\"viewport\")[^>]*>\n?", "", art, flags=re.I)
    art = art.replace("</title>", '</title>\n<meta name="claude:viewport-fit-sides" content="cover">', 1)
    open(os.path.join(run, "artifact.html"), "w", encoding="utf-8").write(art)
    print(f"-> {run}/report.html + artifact.html  (all rivals ahead on {len(by('all'))} checks, "
          f"most on {len(by('most'))}, you lead on {len(by('lead'))})")


if __name__ == "__main__":
    render(sys.argv[1])
