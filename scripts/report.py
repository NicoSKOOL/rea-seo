"""REA SEO, step 3: score teardown.json and render report.html.

Usage: python scripts/report.py runs/<slug>
Reads collected.json + teardown.json (+ plan.json written by Claude, optional).
Writes runs/<slug>/scores.json and runs/<slug>/report.html (self-contained).

Rule: every row is a difference between two sites, never a cause.
"""
import html, json, os, sys
from datetime import date

E = lambda x: html.escape(str(x))  # noqa: E731
LOC = {2840: "United States", 2036: "Australia", 2826: "United Kingdom", 2124: "Canada", 2152: "Chile"}


def g(d, *path):
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d


def bots_allowed(s):
    b = g(s, "agentic", "robots", "bots") or {}
    return sum(v.startswith("allowed") for v in b.values())


def js_free(s):
    o = s["onpage"]
    if o.get("js_free_share") is not None:
        return o["js_free_share"] >= 0.6
    return (o.get("raw_words") or 0) >= 200


def domain_age(s):
    c = g(s, "site_metrics", "created")
    if not c:
        return None
    y, m, d = map(int, c.split("-"))
    return round((date.today() - date(y, m, d)).days / 365.25, 1)


def size_cls(domain):
    """Header font class so long domains stay on one line next to the rank number."""
    n = len(domain or "")
    return "xlong" if n > 24 else "long" if n > 10 else ""


def title_ok(s):
    o = s["onpage"]
    return bool(o.get("title_has_terms")) and 30 <= (o.get("title_len") or 0) <= 65


# (key, label, getter, better: "high" | "low" | "yes" | None (context only), fmt)
AREAS = [
    ("onpage", "On-page SEO", "What Google reads in the HTML", [
        ("title", "Title uses the keyword, 30 to 65 chars", title_ok, "yes", "bool"),
        ("title_len", "Title length", lambda s: g(s, "onpage", "title_len"), None, "chars"),
        ("meta", "Meta description length", lambda s: g(s, "onpage", "meta_description_len"), "high", "chars"),
        ("canon", "Self-referencing canonical", lambda s: g(s, "onpage", "canonical_self"), "yes", "bool"),
        ("h1", "Exactly one H1", lambda s: g(s, "onpage", "h1_count") == 1, "yes", "bool"),
        ("h2", "H2 sections", lambda s: g(s, "onpage", "h2_count"), "high", "num"),
        ("schema", "Schema types on the page", lambda s: len(g(s, "onpage", "schema_types") or []), "high", "num"),
        ("faq", "FAQ schema", lambda s: g(s, "onpage", "has_faq_schema"), "yes", "bool"),
        ("alt", "Images with alt text", lambda s: (g(s, "onpage", "images_with_alt") or 0) / g(s, "onpage", "images")
         if g(s, "onpage", "images") else None, "high", "pct"),
    ]),
    ("agentic", "Agentic SEO / GEO", "Can AI crawlers and answer engines use it", [
        ("bots", "AI crawlers allowed (of 9)", bots_allowed, "high", "num"),
        ("llms", "llms.txt file", lambda s: g(s, "agentic", "llms_txt", "found"), "yes", "bool"),
        ("jsfree", "Main content in the HTML (no JavaScript needed)", js_free, "yes", "bool"),
        ("aio_mentions", "Mentions in Google AI answers", lambda s: g(s, "agentic", "llm_mentions", "mentions"), "high", "num"),
        ("gpt", "Named in ChatGPT's answer", lambda s: s.get("_gpt_mentioned"), "yes", "bool"),
    ]),
    ("backlinks", "Authority & brand", "Who vouches for the site, and who searches for it", [
        ("brand", "Brand-name searches / month", lambda s: g(s, "site_metrics", "brand_volume"), "high", "num"),
        ("age", "Domain age (years)", domain_age, "high", "num"),
        ("rd", "Referring domains (site)", lambda s: g(s, "backlinks", "summary", "referring_domains"), "high", "num"),
        ("page_rd", "Referring domains (ranking page)", lambda s: g(s, "backlinks", "page", "referring_domains"), "high", "num"),
        ("rank", "Domain rank (DataForSEO, 0 to 1000)", lambda s: g(s, "backlinks", "summary", "rank"), "high", "num"),
        ("dofollow", "Dofollow share", lambda s: g(s, "backlinks", "summary", "dofollow_share"), "high", "pct"),
        ("spam", "Backlink spam score", lambda s: g(s, "backlinks", "summary", "backlinks_spam_score"), "low", "num"),
    ]),
    ("structure", "Pages & structure", "How the site is organised", [
        ("urls", "Pages in the sitemap", lambda s: g(s, "structure", "sitemap_urls") or None, "high", "num"),
        ("topical", "Sitemap URLs on this topic", lambda s: g(s, "structure", "topical_urls") if g(s, "structure", "sitemap_found") else None, "high", "num"),
        ("depth", "Clicks deep (URL folders)", lambda s: g(s, "structure", "page_depth"), "low", "num"),
        ("home", "Linked from the homepage", lambda s: g(s, "structure", "page_linked_from_home"), "yes", "bool"),
        ("internal", "Internal links on the page", lambda s: g(s, "onpage", "internal_unique"), "high", "num"),
    ]),
    ("content", "Content", "What the page actually says", [
        ("words", "Words in the HTML", lambda s: g(s, "onpage", "raw_words"), None, "num"),
        ("headings", "Headings (H1 to H4)", lambda s: len(g(s, "onpage", "headings") or []), "high", "num"),
        ("terms", "Keyword in the visible text", lambda s: g(s, "onpage", "has_term_in_raw"), "yes", "bool"),
    ]),
    ("speed", "Speed", "Mobile Lighthouse (lab test)", [
        ("perf", "Performance score", lambda s: g(s, "speed", "performance"), "high", "num"),
        ("lcp", "Largest paint", lambda s: g(s, "speed", "lcp_ms"), "low", "ms"),
        ("cls", "Layout shift", lambda s: g(s, "speed", "cls"), "low", "cls"),
    ]),
]


def fmt(v, kind):
    if v is None:
        return "not checked"
    if kind == "bool":
        return "Yes" if v else "No"
    if kind == "pct":
        return f"{v * 100:.0f}%"
    if kind == "ms":
        return f"{v / 1000:.1f}s"
    if kind == "cls":
        return f"{v:.3f}"
    if kind == "num" and isinstance(v, float) and v < 10 and v != int(v):
        return f"{v:.1f}"
    if kind == "chars":
        return f"{v} chars"
    v = float(v)
    if v >= 1e6:
        return f"{v / 1e6:.1f}M"
    if v >= 10000:
        return f"{v / 1000:.0f}K"
    if v >= 1000:
        return f"{v / 1000:.1f}K".replace(".0K", "K")
    return f"{v:,.0f}"


def leader(a, b, better):
    if better is None or a is None or b is None:
        return "ctx"
    if better == "yes":
        a, b = bool(a), bool(b)
        return "tie" if a == b else ("rival" if a else "you")
    if a == b:
        return "tie"
    hi = a > b
    return ("rival" if hi else "you") if better == "high" else ("you" if hi else "rival")


def score(td):
    gpt = td.get("chatgpt") or {}
    for side in ("rival", "you"):
        s = td["sites"][side]
        s["_gpt_mentioned"] = (gpt.get("mentioned") or {}).get(s["root"]) if "mentioned" in gpt else None
    out = []
    for key, name, sub, rows in AREAS:
        res = []
        for k, label, fn, better, kind in rows:
            vals = []
            for side in ("rival", "you"):
                try:
                    vals.append(fn(td["sites"][side]))
                except Exception:  # noqa: BLE001
                    vals.append(None)
            res.append({"key": k, "label": label, "rival": vals[0], "you": vals[1], "kind": kind,
                        "better": better, "lead": leader(vals[0], vals[1], better)})
        r = sum(x["lead"] == "rival" for x in res)
        y = sum(x["lead"] == "you" for x in res)
        out.append({"key": key, "name": name, "sub": sub, "rows": res, "rival_wins": r, "you_wins": y,
                    "lead": "tie" if r == y else ("rival" if r > y else "you")})
    return out


# ---------- rendering ----------

def bar_pair(row):
    a, b = row["rival"], row["you"]
    if row["kind"] in ("bool", "chars") or not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return ""
    if isinstance(a, bool) or isinstance(b, bool):
        return ""
    m = max(a, b) or 1
    return (f'<div class="bars"><i class="b-r" style="width:{max(2, a / m * 100):.0f}%"></i>'
            f'<i class="b-y" style="width:{max(2, b / m * 100):.0f}%"></i></div>')


LEAD_TXT = {"rival": "#1 leads", "you": "You lead", "tie": "Even", "ctx": "Context"}

# When the rival is not the #1 result (the #1 was a directory, or you are #1), say "rival", not "#1".
RIVAL_WORDS = [("The #1 result", "The rival"), ("#1 leads", "Rival leads"), ('class="val v-r">#1<', 'class="val v-r">Rival<'),
               ("the #1's", "the rival's"), ("the #1 but", "the rival but"), ("the #1 has", "the rival has"),
               ("against the #1 result", "against the rival"), ("The #1:", "The rival:"), (" (#1)", " (rival)"),
               ("#1 vs you", "rival vs you"), ("links to the #1", "links to the rival")]


def relabel(text, rival):
    """Swap '#1' wording for 'rival' when the rival page is not position 1."""
    if (rival or {}).get("position") == 1:
        return text
    for a, b in RIVAL_WORDS:
        text = text.replace(a, b)
    return text


def area_html(a):
    rows = []
    for r in a["rows"]:
        rows.append(f'''<div class="row lead-{r["lead"]}">
  <div class="lab">{E(r["label"])}{bar_pair(r)}</div>
  <div class="val v-r">{E(fmt(r["rival"], r["kind"]))}</div>
  <div class="val v-y">{E(fmt(r["you"], r["kind"]))}</div>
  <div class="chip c-{r["lead"]}">{LEAD_TXT[r["lead"]]}</div>
</div>''')
    return f'''<section class="area" id="{a["key"]}">
 <header><div><h3>{E(a["name"])}</h3><p>{E(a["sub"])}</p></div>
 <div class="tally"><span class="t-r">{a["rival_wins"]}</span><em>vs</em><span class="t-y">{a["you_wins"]}</span></div></header>
 <div class="row head"><div></div><div class="val v-r">#1</div><div class="val v-y">You</div><div></div></div>
 {"".join(rows)}
</section>'''


def render(run):
    col = json.load(open(os.path.join(run, "collected.json")))
    td = json.load(open(os.path.join(run, "teardown.json")))
    plan_p = os.path.join(run, "plan.json")
    plan = json.load(open(plan_p)) if os.path.exists(plan_p) else {}
    areas = score(td)
    json.dump(areas, open(os.path.join(run, "scores.json"), "w"), indent=1, ensure_ascii=False, default=str)
    R, Y = td["sites"]["rival"], td["sites"]["you"]
    rw = sum(a["lead"] == "rival" for a in areas)
    yw = sum(a["lead"] == "you" for a in areas)

    board = "".join(f'<a class="cell l-{a["lead"]}" href="#{a["key"]}"><b>{E(a["name"])}</b>'
                    f'<span>{LEAD_TXT[a["lead"]] if a["lead"] != "tie" else "Even"}</span>'
                    f'<small>{a["rival_wins"]} vs {a["you_wins"]}</small></a>' for a in areas)

    # top-10 strip
    top = sorted([r for r in col["results"] if r.get("position")], key=lambda r: r["position"])
    seen, strip = set(), []
    for r in top:
        if r["position"] in seen:
            continue
        seen.add(r["position"])
        cls = "s-r" if r["url"] == td["rival_url"] else ("s-y" if r.get("is_target") else "")
        rd = g(r, "links", "referring_domains")
        drd = g(r, "site", "referring_domains")
        perf = g(r, "lighthouse", "performance")
        strip.append(f'<li class="{cls}"><span class="pos">{r["position"]}</span><span class="dom">{E(r["root"])}</span>'
                     f'<span class="m">{fmt(drd, "num")} <em>site RDs</em></span>'
                     f'<span class="m">{fmt(rd, "num").replace("not checked", "n/a")} <em>page RDs</em></span>'
                     f'<span class="m">{fmt(perf, "num").replace("not checked", "n/a")} <em>speed</em></span></li>')

    gap = td.get("link_gap") or {}
    gap_items = "".join(f'<li><span>{E(i["domain"])}</span><em>rank {i["rank"]}</em></li>' for i in gap.get("items", [])[:12])

    def mentions(side):
        return g(td["sites"][side], "agentic", "llm_mentions", "mentions")
    others = {}
    for side in ("rival", "you"):
        for x in g(td["sites"][side], "agentic", "llm_mentions", "raw_total", "sources_domain") or []:
            d = x["key"].removeprefix("www.")
            if d not in (R["root"], Y["root"]):
                others[d] = max(others.get(d, 0), x["mentions"])
    srcs = [{"key": R["root"], "mentions": mentions("rival")}, {"key": Y["root"], "mentions": mentions("you")}]
    srcs = [x for x in srcs if x["mentions"] is not None] + [
        {"key": d, "mentions": m} for d, m in sorted(others.items(), key=lambda kv: -kv[1])[:6]]
    mx = max([s["mentions"] for s in srcs] or [1]) or 1

    def hl(d):
        d2 = d.removeprefix("www.")
        return "s-r" if d2 == R["root"] else ("s-y" if d2 == Y["root"] else "")
    aio = "".join(f'<li class="{hl(s["key"])}"><span>{E(s["key"])}</span>'
                  f'<i style="width:{s["mentions"] / mx * 100:.0f}%"></i><b>{s["mentions"]}</b></li>' for s in srcs)
    gp = td.get("chatgpt") or {}
    gpt_line = ("ChatGPT's answer cited: " + ", ".join(gp.get("sources", [])[:8]) + ". "
                + " ".join(f"{d}: {'cited' if c else 'not cited'}." for d, c in (gp.get("cited") or {}).items())) \
        if gp.get("sources") is not None else "ChatGPT: not checked"

    tg = td.get("topic_gap") or {}
    moves = plan.get("moves") or []
    TAG = {"week": "Do this week", "time": "Takes time", "dont": "Don't copy", "keep": "Keep doing"}
    def move(i, m):
        steps = "".join(f'<li><label><input type="checkbox" data-k="{i}-{j}"><span>{E(x)}</span></label></li>'
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
    n_steps = sum(len(m.get("steps") or []) for m in moves)

    head = plan.get("headline") or f"#1 leads in {rw} of 6 areas. You lead in {yw}."
    dek = plan.get("dek") or ""
    cost = (td["cost"].get("total_usd") or 0) + (td["cost"].get("collect_usd") or 0)
    loc = LOC.get(col["location_code"], col["location_code"])
    tpl = open(os.path.join(os.path.dirname(__file__), "..", "templates", "rea_report.html")).read()
    rep = {
        "{{KW}}": E(col["keyword"]), "{{LOC}}": E(loc), "{{DATE}}": date.today().strftime("%d %b %Y"),
        "{{COST}}": f"${cost:.2f}", "{{R_ROOT}}": E(R["root"]), "{{Y_ROOT}}": E(Y["root"]),
        "{{R_LONG}}": size_cls(R["root"]), "{{Y_LONG}}": size_cls(Y["root"]),
        "{{R_POS}}": E(R.get("position") or "?"), "{{Y_POS}}": E(Y.get("position") or "?"),
        "{{R_URL}}": E(td["rival_url"]), "{{Y_URL}}": E(td["you_url"]),
        "{{RW}}": str(rw), "{{YW}}": str(yw), "{{HEAD}}": E(head), "{{DEK}}": E(dek),
        "{{BOARD}}": board, "{{AREAS}}": "".join(area_html(a) for a in areas),
        "{{STRIP}}": "".join(strip), "{{GAP_TOTAL}}": fmt(gap.get("total"), "num"), "{{GAP}}": gap_items,
        "{{AIO}}": aio or "<li>not checked</li>", "{{GPT}}": E(gpt_line),
        "{{TOPICS}}": " ".join(f"<span>{E(t)}</span>" for t in (tg.get("rival_only") or [])[:24]) or "<span>none</span>",
        "{{NSTEPS}}": str(n_steps), "{{SLUG}}": E(os.path.basename(run.rstrip("/"))),
        "{{MOVES}}": moves_html or '<li class="mv"><div><p>Run Claude on scores.json to write plan.json.</p></div></li>',
    }
    for k, v in rep.items():
        tpl = tpl.replace(k, v)
    out = os.path.join(run, "report.html")
    open(out, "w").write(relabel(tpl, R))
    print(relabel(f"-> {out}  (#1 leads {rw} areas, you lead {yw})", R))


if __name__ == "__main__":
    render(sys.argv[1])
