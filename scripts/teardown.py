"""REA SEO, step 2: deep teardown of the #1 site against your site.

Run after collect.py (which gives the top-10 strip and page-level data).

Usage:
  python scripts/teardown.py runs/<slug> [--rival https://rival.com/page]

Adds runs/<slug>/teardown.json with six areas for both sites:
  onpage, agentic (AI crawlers, llms.txt, JS-free visibility, AI answers), backlinks,
  structure (sitemap, folders, depth, homepage link), content (topics), speed (from collect).
Free checks fetch the live site directly; paid checks use DataForSEO (costs logged).
"""
import argparse, json, os, re, sys
from collections import Counter
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from dfs import post, first_result, COST  # noqa: E402

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36 REA-SEO/1.0"
AI_BOTS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot",
           "PerplexityBot", "Google-Extended", "CCBot", "Applebot-Extended"]
LOC_NAME = {2840: "United States", 2036: "Australia", 2826: "United Kingdom", 2124: "Canada", 2152: "Chile"}


def get(url, timeout=25):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout, allow_redirects=True)
        return r
    except Exception:  # noqa: BLE001
        return None


def origin(url):
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def words(text):
    return re.findall(r"\w+", (text or "").lower())


# ---------- on-page (raw HTML, no JavaScript) ----------

def schema_types(soup):
    types, raw_blocks = [], 0
    for s in soup.find_all("script", type="application/ld+json"):
        raw_blocks += 1
        try:
            data = json.loads(s.string or "")
        except Exception:  # noqa: BLE001
            types.append("(invalid JSON-LD)")
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                t = x.get("@type")
                if t:
                    types.extend(t if isinstance(t, list) else [t])
                for v in x.values():
                    if isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(x, list):
                stack.extend(x)
    return sorted(set(map(str, types))), raw_blocks


def onpage(url, terms, rendered_words):
    r = get(url)
    if r is None or r.status_code >= 400:
        return {"error": f"fetch failed ({getattr(r, 'status_code', 'no response')})"}
    soup = BeautifulSoup(r.text, "html.parser")
    meta = lambda **kw: (soup.find("meta", attrs=kw) or {}).get("content")  # noqa: E731
    title = (soup.title.string or "").strip() if soup.title else ""
    canon = (soup.find("link", rel="canonical") or {}).get("href")
    heads = [(int(h.name[1]), " ".join(h.get_text(" ").split())) for h in soup.find_all(re.compile("^h[1-4]$"))]
    types, blocks = schema_types(soup)
    for t in soup(["script", "style", "noscript", "template"]):
        t.decompose()
    text = soup.get_text(" ")
    raw_words = len(words(text))
    host = urlparse(r.url).netloc.removeprefix("www.")
    links = [urljoin(r.url, a.get("href")) for a in soup.find_all("a", href=True)]
    internal = [u for u in links if urlparse(u).netloc.removeprefix("www.") == host]
    imgs = soup.find_all("img")
    tl = title.lower()
    h1s = [t for lvl, t in heads if lvl == 1]
    return {
        "final_url": r.url, "status": r.status_code, "html_kb": round(len(r.content) / 1024),
        "title": title, "title_len": len(title), "title_has_terms": sum(t in tl for t in terms),
        "meta_description": meta(name="description"),
        "meta_description_len": len(meta(name="description") or ""),
        "canonical": canon, "canonical_self": bool(canon) and canon.rstrip("/") == r.url.rstrip("/"),
        "robots_meta": meta(name="robots"), "og_title": bool(meta(property="og:title")),
        "og_image": bool(meta(property="og:image")), "lang": (soup.html or {}).get("lang") if soup.html else None,
        "hreflang": len(soup.find_all("link", hreflang=True)),
        "h1": h1s, "h1_count": len(h1s), "h2_count": sum(1 for l, _ in heads if l == 2),
        "h3_count": sum(1 for l, _ in heads if l == 3), "headings": heads[:80],
        "schema_types": types, "schema_blocks": blocks,
        "has_faq_schema": "FAQPage" in types,
        "internal_links": len(internal), "internal_unique": len(set(u.split("#")[0] for u in internal)),
        "external_links": len(links) - len(internal),
        "images": len(imgs), "images_with_alt": sum(1 for i in imgs if (i.get("alt") or "").strip()),
        "raw_words": raw_words, "rendered_words": rendered_words,
        "js_free_share": round(min(1, raw_words / rendered_words), 2) if rendered_words else None,
        "has_term_in_raw": all(t in text.lower() for t in terms) if terms else None,
    }


# ---------- agentic / GEO ----------

def robots(base):
    r = get(urljoin(base, "/robots.txt"))
    if r is None or r.status_code >= 400:
        return {"found": False, "bots": {b: "allowed (no robots.txt)" for b in AI_BOTS}, "sitemaps": []}
    groups, cur, sitemaps = {}, [], []
    last_was_agent = False
    for line in r.text.splitlines():
        line = line.split("#")[0].strip()
        if ":" not in line:
            continue
        k, v = [x.strip() for x in line.split(":", 1)]
        k = k.lower()
        if k == "user-agent":
            if not last_was_agent:
                cur = []
            cur.append(v.lower())
            groups.setdefault(v.lower(), [])
            last_was_agent = True
        else:
            last_was_agent = False
            if k == "sitemap":
                sitemaps.append(v)
            elif k in ("allow", "disallow"):
                for ua in cur:
                    groups[ua].append((k, v))

    def verdict(bot):
        rules = groups.get(bot.lower())
        src = "own rule"
        if rules is None:
            rules, src = groups.get("*", []), "via *"
        blocked = any(k == "disallow" and v == "/" for k, v in rules)
        reopened = any(k == "allow" and v == "/" for k, v in rules)
        return ("blocked" if blocked and not reopened else "allowed") + f" ({src})"
    return {"found": True, "bots": {b: verdict(b) for b in AI_BOTS}, "sitemaps": sitemaps}


def llms_txt(base):
    r = get(urljoin(base, "/llms.txt"))
    ok = bool(r is not None and r.status_code == 200 and "<html" not in r.text[:500].lower() and len(r.text) > 20)
    return {"found": ok, "bytes": len(r.text) if ok else 0}


def ai_answers(kw, loc, lang, roots):
    """Does ChatGPT's answer for the keyword cite either site? (DataForSEO LLM scraper)"""
    try:
        res = first_result(post("ai_optimization/chat_gpt/llm_scraper/live/advanced",
                                [{"keyword": kw, "location_name": LOC_NAME.get(loc, "United States"),
                                  "language_code": lang, "force_web_search": True}], timeout=240))
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:200]}
    if not res:
        return {"error": "no result"}
    blob = json.dumps(res[0]).lower()
    urls = re.findall(r'"url":\s*"(https?://[^"]+)"', json.dumps(res[0]))
    doms = Counter(urlparse(u).netloc.removeprefix("www.") for u in urls)
    return {"cited": {r: any(d == r or d.endswith("." + r) for d in doms) for r in roots},
            "mentioned": {r: (r in blob) or (r.split(".")[0] in blob) for r in roots},
            "sources": [d for d, _ in doms.most_common(12)]}


def llm_mentions(root, loc, lang):
    try:
        res = first_result(post("ai_optimization/llm_mentions/aggregated_metrics/live",
                                [{"target": [{"domain": root}], "language_code": lang,
                                  "location_name": LOC_NAME.get(loc, "United States"), "platform": "google"}]))
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:200]}
    if not res:
        return {"error": "no result"}
    tot = (res[0].get("total") or {})
    plat = tot.get("platform") or []
    mentions = sum((p.get("mentions") or 0) for p in plat) if isinstance(plat, list) else None
    return {"mentions": mentions, "raw_total": {k: tot[k] for k in list(tot)[:6]}}


# ---------- backlinks ----------

def bl_summary(root):
    res = first_result(post("backlinks/summary/live", [{"target": root, "include_subdomains": True}]))
    if not res:
        return {}
    x = res[0]
    return {k: x.get(k) for k in ("rank", "backlinks", "referring_domains", "referring_main_domains",
                                  "referring_ips", "backlinks_spam_score", "broken_backlinks")} | {
        "dofollow_share": round(1 - (x.get("referring_domains_nofollow") or 0) / x["referring_domains"], 2)
        if x.get("referring_domains") else None}


def top_refdomains(root, n=8):
    res = first_result(post("backlinks/referring_domains/live",
                            [{"target": root, "limit": 40, "order_by": ["rank,desc"]}]))
    items = [i for i in ((res[0].get("items") or []) if res else []) if (i.get("backlinks_spam_score") or 0) < 40]
    return [{"domain": i.get("domain"), "rank": i.get("rank"), "backlinks": i.get("backlinks")} for i in items[:n]]


def link_gap(rival, you, n=15):
    """Domains linking to the rival but not to you."""
    res = first_result(post("backlinks/domain_intersection/live",
                            [{"targets": {"1": rival}, "exclude_targets": [you], "limit": 60,
                              "order_by": ["1.rank,desc"]}]))
    out = []
    for i in (res[0].get("items") or []) if res else []:
        d = (i.get("domain_intersection") or {}).get("1") or {}
        if (d.get("backlinks_spam_score") or 0) >= 40 or len(out) >= n:
            continue
        out.append({"domain": d.get("target"), "rank": d.get("rank"), "backlinks": d.get("backlinks"),
                    "first_seen": (d.get("first_seen") or "")[:10]})
    return {"total": (res[0].get("total_count") if res else None), "items": out}


# ---------- pages & structure ----------

def sitemap_urls(base, hinted, cap=6000):
    seen, urls = set(), []
    queue = list(hinted) or [urljoin(base, p) for p in
                                     ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml", "/sitemap/sitemap.xml")]
    while queue and len(urls) < cap and len(seen) < 40:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        r = get(sm)
        if r is None or r.status_code >= 400:
            continue
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError:
            continue
        locs = [e.text.strip() for e in root.iter() if e.tag.endswith("loc") and e.text]
        if root.tag.endswith("sitemapindex"):
            queue.extend(locs)
        else:
            urls.extend(locs)
    return urls[:cap], len(seen)


def structure(base, page_url, hinted_sitemaps, terms):
    urls, n_maps = sitemap_urls(base, hinted_sitemaps)
    paths = [urlparse(u).path for u in urls]
    depth = Counter(len([p for p in x.split("/") if p]) for x in paths)
    folders = Counter((x.strip("/").split("/")[0] or "(home)") for x in paths)
    topical = [u for u in urls if terms and all(t in u.lower() for t in terms[:2])]
    home = get(base)
    linked_from_home = False
    if home is not None and home.status_code < 400:
        hs = BeautifulSoup(home.text, "html.parser")
        target_path = urlparse(page_url).path.rstrip("/") or "/"
        linked_from_home = any((urlparse(urljoin(home.url, a["href"])).path.rstrip("/") or "/") == target_path
                               for a in hs.find_all("a", href=True))
    pdepth = len([p for p in urlparse(page_url).path.split("/") if p])
    return {"sitemap_found": bool(urls), "sitemap_files": n_maps, "sitemap_urls": len(urls),
            "top_folders": folders.most_common(8), "depth": sorted(depth.items()),
            "topical_urls": len(topical), "topical_examples": topical[:6],
            "page_depth": pdepth, "page_linked_from_home": linked_from_home}


# ---------- content ----------

def topic_gap(rival_heads, you_heads):
    def toks(heads):
        out = set()
        for _, t in heads:
            out |= {w for w in words(t) if len(w) > 3}
        return out
    r, y = toks(rival_heads), toks(you_heads)
    return {"rival_only": sorted(r - y)[:40], "you_only": sorted(y - r)[:40], "shared": len(r & y)}


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--rival", help="rival page URL (default: the #1 web result)")
    a = ap.parse_args()
    col = json.load(open(os.path.join(a.run, "collected.json")))
    kw, loc, lang, terms = col["keyword"], col["location_code"], col["language_code"], col["terms"]
    res = col["results"]
    you = next((r for r in res if r.get("is_target")), None)
    if not you:
        raise SystemExit("No target page in collected.json: rerun collect.py with --site (and --page).")
    rival = None
    if a.rival:
        rival = next((r for r in res if r["url"].rstrip("/") == a.rival.rstrip("/")), None) or {
            "url": a.rival, "domain": urlparse(a.rival).netloc, "root": urlparse(a.rival).netloc.removeprefix("www."),
            "position": None, "kind": "web"}
    else:
        rival = next(r for r in sorted(res, key=lambda r: r["position"] or 99)
                     if r["kind"] == "web" and not r.get("is_target"))
    pair = {"rival": rival, "you": you}
    out = {"keyword": kw, "rival_url": rival["url"], "you_url": you["url"], "sites": {}}

    for side, r in pair.items():
        print(f"[{side}] {r['url']}")
        base = origin(r["url"])
        rendered = (r.get("content") or {}).get("word_count")
        rb = robots(base)
        out["sites"][side] = {
            "root": r["root"], "position": r.get("position"),
            "onpage": onpage(r["url"], terms, rendered),
            "agentic": {"robots": rb, "llms_txt": llms_txt(base),
                        "in_ai_overview": any((x.get("domain") or "").removeprefix("www.").endswith(r["root"])
                                              for x in col["serp"].get("ai_overview_refs") or []),
                        "llm_mentions": llm_mentions(r["root"], loc, lang)},
            "backlinks": {"summary": bl_summary(r["root"]), "top_domains": top_refdomains(r["root"]),
                          "page": r.get("links") or {}, "anchors": r.get("anchors") or {}},
            "structure": structure(base, r["url"], rb.get("sitemaps") or [], terms),
            "speed": r.get("lighthouse") or {},
            "site_metrics": r.get("site") or {},
        }
    print("[gap] link gap + ChatGPT answer + topic gap")
    out["link_gap"] = link_gap(rival["root"], you["root"])
    out["chatgpt"] = ai_answers(kw, loc, lang, [rival["root"], you["root"]])
    out["topic_gap"] = topic_gap(out["sites"]["rival"]["onpage"].get("headings") or [],
                                 out["sites"]["you"]["onpage"].get("headings") or [])
    out["cost"] = {"total_usd": round(COST["total"], 4), "calls": len(COST["calls"]),
                   "collect_usd": (col.get("cost") or {}).get("total_usd")}
    path = os.path.join(a.run, "teardown.json")
    json.dump(out, open(path, "w"), indent=1, ensure_ascii=False)
    print(f"done -> {path}  teardown cost ${COST['total']:.3f}")


if __name__ == "__main__":
    main()
