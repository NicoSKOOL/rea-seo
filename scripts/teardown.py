"""REA SEO step 7: free live checks on your page and each rival page + merge the MCP numbers. Free.

Usage: python3 teardown.py rea-seo/<slug>

Reads  run.json, rivals.json, serp.json, targets.json, mcp.json      Writes teardown.json
Free checks fetch the live sites directly: HTML on-page, robots.txt AI crawlers, llms.txt,
sitemap, homepage link, shared topics. Every row is a difference, never a cause.
"""
import json, os, re, sys
from collections import Counter
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import UA, load, save, query_terms  # noqa: E402

AI_BOTS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot",
           "PerplexityBot", "Google-Extended", "CCBot", "Applebot-Extended"]


def get(url, timeout=25):
    try:
        return requests.get(url, headers={"User-Agent": UA}, timeout=timeout, allow_redirects=True)
    except Exception:  # noqa: BLE001
        return None


def origin(url):
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def words(text):
    return re.findall(r"\w+", (text or "").lower())


def num(v):
    if v in (None, ""):
        return None
    try:
        return float(v) if "." in str(v) else int(v)
    except (TypeError, ValueError):
        return None


# ---------- on-page ----------

def schema_types(soup):
    types, blocks = [], 0
    for s in soup.find_all("script", type="application/ld+json"):
        blocks += 1
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
                stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
            elif isinstance(x, list):
                stack.extend(x)
    return sorted(set(map(str, types))), blocks


def onpage(url, terms):
    r = get(url)
    if r is None or r.status_code >= 400:
        return {"error": f"fetch failed ({getattr(r, 'status_code', 'no response')})"}
    soup = BeautifulSoup(r.text, "html.parser")
    meta = lambda **kw: (soup.find("meta", attrs=kw) or {}).get("content")  # noqa: E731
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    canon = (soup.find("link", rel="canonical") or {}).get("href")
    heads = [(int(h.name[1]), " ".join(h.get_text(" ").split())) for h in soup.find_all(re.compile("^h[1-4]$"))]
    types, blocks = schema_types(soup)
    for t in soup(["script", "style", "noscript", "template"]):
        t.decompose()
    text = soup.get_text(" ")
    host = urlparse(r.url).netloc.removeprefix("www.")
    links = [urljoin(r.url, a.get("href")) for a in soup.find_all("a", href=True)]
    internal = [u for u in links if urlparse(u).netloc.removeprefix("www.") == host]
    imgs = soup.find_all("img")
    tl, low = title.lower(), text.lower()
    h1s = [t for lvl, t in heads if lvl == 1]
    md = meta(name="description") or ""
    return {
        "final_url": r.url, "status": r.status_code, "html_kb": round(len(r.content) / 1024),
        "title": title, "title_len": len(title), "title_has_terms": sum(t in tl for t in terms),
        "meta_description": md, "meta_description_len": len(md),
        "canonical": canon, "canonical_self": bool(canon) and urljoin(r.url, canon).rstrip("/") == r.url.rstrip("/"),
        "robots_meta": meta(name="robots"), "og_title": bool(meta(property="og:title")),
        "og_image": bool(meta(property="og:image")),
        "h1": h1s, "h1_count": len(h1s), "h2_count": sum(1 for l, _ in heads if l == 2),
        "h3_count": sum(1 for l, _ in heads if l == 3), "headings": heads[:80],
        "schema_types": types, "schema_blocks": blocks, "has_faq_schema": "FAQPage" in types,
        "internal_links": len(internal), "internal_unique": len({u.split("#")[0] for u in internal}),
        "external_links": len(links) - len(internal),
        "images": len(imgs), "images_with_alt": sum(1 for i in imgs if (i.get("alt") or "").strip()),
        "raw_words": len(words(text)), "rendered_words": None, "js_free_share": None,
        "has_term_in_raw": all(t in low for t in terms) if terms else None,
        "term_mentions": sum(low.count(t) for t in terms),
    }


# ---------- agentic / GEO ----------

def robots(base):
    r = get(urljoin(base, "/robots.txt"))
    if r is None or r.status_code >= 400:
        return {"found": False, "bots": {b: "allowed (no robots.txt)" for b in AI_BOTS}, "sitemaps": []}
    groups, cur, sitemaps, last_agent = {}, [], [], False
    for line in r.text.splitlines():
        line = line.split("#")[0].strip()
        if ":" not in line:
            continue
        k, v = [x.strip() for x in line.split(":", 1)]
        k = k.lower()
        if k == "user-agent":
            if not last_agent:
                cur = []
            cur.append(v.lower())
            groups.setdefault(v.lower(), [])
            last_agent = True
        else:
            last_agent = False
            if k == "sitemap":
                sitemaps.append(v)
            elif k in ("allow", "disallow"):
                for ua in cur:
                    groups[ua].append((k, v))

    def verdict(bot):
        rules, src = groups.get(bot.lower()), "own rule"
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


# ---------- structure ----------

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
            rt = ET.fromstring(r.content)
        except ET.ParseError:
            continue
        locs = [e.text.strip() for e in rt.iter() if e.tag.endswith("loc") and e.text]
        if rt.tag.endswith("sitemapindex"):
            queue.extend(locs)
        else:
            urls.extend(locs)
    return urls[:cap], len(seen)


def structure(base, page_url, hinted, terms):
    urls, n_maps = sitemap_urls(base, hinted)
    paths = [urlparse(u).path for u in urls]
    folders = Counter((x.strip("/").split("/")[0] or "(home)") for x in paths)
    key = [t for t in terms if len(t) > 2][:2] or terms[:1]
    topical = [u for u in urls if key and all(t in u.lower() for t in key)]
    home = get(base)
    linked = False
    if home is not None and home.status_code < 400:
        hs = BeautifulSoup(home.text, "html.parser")
        tp = urlparse(page_url).path.rstrip("/") or "/"
        linked = tp == "/" or any((urlparse(urljoin(home.url, a["href"])).path.rstrip("/") or "/") == tp
                                  for a in hs.find_all("a", href=True))
    return {"sitemap_found": bool(urls), "sitemap_files": n_maps, "sitemap_urls": len(urls),
            "top_folders": folders.most_common(8), "topical_urls": len(topical),
            "topical_examples": topical[:6],
            "page_depth": len([p for p in urlparse(page_url).path.split("/") if p]),
            "page_linked_from_home": linked}


def shared_topics(rival_heads, you_heads):
    """Heading words used by at least two rivals that your headings never use."""
    def toks(heads):
        out = set()
        for _, t in heads:
            out |= {w for w in words(t) if len(w) > 3 and not w.isdigit()}
        return out
    y = toks(you_heads)
    c = Counter()
    for h in rival_heads:
        c.update(toks(h) - y)
    need = 2 if len(rival_heads) > 1 else 1
    return sorted(w for w, k in c.items() if k >= need)[:40]


# ---------- main ----------

def main(run):
    cfg, rv, serp = load(f"{run}/run.json"), load(f"{run}/rivals.json"), load(f"{run}/serp.json", {})
    tg, m = load(f"{run}/targets.json"), load(f"{run}/mcp.json", {})
    if not tg:
        sys.exit("Run prepare.py first.")
    kw, terms = cfg["primary"], query_terms(cfg["primary"])
    types, ms = m.get("page_types") or {}, m.get("sites") or {}
    aio = {(d or "").removeprefix("www.") for d in serp.get("ai_overview_refs") or []}
    pack = serp.get("local_pack") or []

    sites = []
    for t in tg["sites"]:
        print(f"[{t['role']}] {t['url']}")
        d = ms.get(t["root"]) or {}
        base = origin(t["url"])
        rb = robots(base)
        rd, nf = num(d.get("referring_domains")), num(d.get("referring_domains_nofollow"))
        g = d.get("gbp") or {}
        name = (g.get("name") or t["brand"] or "").lower()
        sites.append({
            "role": t["role"], "root": t["root"], "brand": t["brand"], "url": t["url"],
            "position": t["position"], "live_position": t.get("live_position"),
            "page_type": types.get(t["url"]),
            "onpage": onpage(t["url"], terms),
            "agentic": {"robots": rb, "llms_txt": llms_txt(base),
                        "in_ai_overview": any(x == t["root"] or x.endswith("." + t["root"]) for x in aio),
                        "llm_mentions": num(d.get("llm_mentions"))},
            "backlinks": {"rank": num(d.get("rank")), "referring_domains": rd,
                          "spam_score": num(d.get("spam_score")),
                          "dofollow_share": round(1 - (nf or 0) / rd, 2) if rd else None,
                          "page_referring_domains": num(d.get("page_referring_domains"))},
            "structure": structure(base, t["url"], rb.get("sitemaps") or [], terms),
            "speed": {k: num(d.get(k)) for k in ("performance", "lcp_ms", "cls")},
            "site_metrics": {"created": d.get("created"), "brand_volume": num(d.get("brand_volume")),
                             "etv": num(d.get("etv"))},
            "gbp": {**{k: g.get(k) for k in ("name", "city", "category", "claimed")},
                    **{k: num(g.get(k)) for k in ("extra_categories", "rating", "reviews", "photos", "services")},
                    "in_pack": any(name and (name in (p.get("title") or "").lower()
                                            or (p.get("title") or "").lower() in name) for p in pack)},
        })

    rows = [{**x, "page_type": types.get(x["url"], "other")} for x in tg["rows"]]
    gap = m.get("link_gap") or {}
    gp = m.get("chatgpt") or {}
    srcs = [d.removeprefix("www.") for d in gp.get("sources") or []]
    roots = [s["root"] for s in sites]
    you = sites[0]
    out = {
        "site": cfg["site"], "brand": cfg["brand"], "keyword": kw,
        "location": cfg["location_name"], "serp_location": cfg["serp_location"],
        "matrix": {"keywords": rv["keywords"], "you": rv["you"]["positions"],
                   "rivals": [{k: x[k] for k in ("root", "beats", "ranked", "avg", "positions")} for x in rv["rivals"]],
                   "others": [{k: x[k] for k in ("root", "kind", "beats", "avg")} for x in rv.get("others") or []]},
        "serp": {"rows": rows, "features": serp.get("features") or [], "local_pack": pack,
                 "type_counts": Counter(x["page_type"] for x in rows).most_common()},
        "sites": sites,
        "link_gap": {"total": num(gap.get("total")),
                     "items": [{"domain": i.get("domain"), "rank": num(i.get("rank")), "spam": num(i.get("spam"))}
                               for i in gap.get("items") or []][:15]},
        "chatgpt": {"sources": srcs, "mentioned": gp.get("mentioned") or {},
                    "cited": {r: any(d == r or d.endswith("." + r) for d in srcs) for r in roots}},
        "shared_topics": shared_topics([s["onpage"].get("headings") or [] for s in sites[1:]],
                                       you["onpage"].get("headings") or []),
        "calls": m.get("calls"),
    }
    save(f"{run}/teardown.json", out)
    print(f"done -> {run}/teardown.json")


if __name__ == "__main__":
    main(sys.argv[1].rstrip("/\\"))
