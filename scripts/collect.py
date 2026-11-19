"""SERP Autopsy, step 1: collect every measurable signal for a keyword's top 10.

Usage:
  python scripts/collect.py --keyword "claude seo" --site airankingskool.com \
      [--page https://airankingskool.com/learn/claude-seo/] [--location 2840] [--language en]

Writes runs/<slug>/collected.json. All numbers come from DataForSEO (third-party
estimates) or yt-dlp. Nothing here is a Google-internal signal.
"""
import argparse, json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(__file__))
from dfs import post, first_result, COST  # noqa: E402

PLATFORMS = {"youtube.com": "video", "reddit.com": "forum", "quora.com": "forum",
             "github.com": "platform", "linkedin.com": "platform", "medium.com": "platform",
             "x.com": "platform", "twitter.com": "platform", "facebook.com": "platform",
             "wikipedia.org": "platform", "substack.com": "platform", "tiktok.com": "video"}
STOP = {"the", "a", "an", "for", "to", "of", "and", "in", "on", "with", "how", "what", "is",
        "best", "vs", "your", "my", "i", "you", "it", "by", "at", "or", "do", "does"}


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def root(domain):
    d = domain.lower().removeprefix("www.")
    parts = d.split(".")
    return ".".join(parts[-3:]) if len(parts) > 2 and len(parts[-2]) <= 3 else ".".join(parts[-2:])


def kind_of(domain):
    r = root(domain)
    for k, v in PLATFORMS.items():
        if r == k or r.endswith("." + k):
            return v
    return "web"


def query_terms(q):
    return [t for t in re.findall(r"[a-z0-9]+", q.lower()) if t not in STOP]


def brand_of(r):
    name = (r.get("website_name") or "").strip()
    name = re.split(r"\s+[-|:]\s+", name)[0]
    if not name or "." in name:
        name = r["root"].split(".")[0]
    return name.lower()


def pmap(fn, items, workers=8):
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(fn, items))


# ---------- collectors ----------

def resolve_goto(item):
    """Follow a google.com/goto wrapper to the real URL; fall back to the breadcrumb."""
    import requests
    try:
        r = requests.Session().get(item["url"], allow_redirects=True, timeout=20,
                                   headers={"User-Agent": "Mozilla/5.0 (Macintosh) Chrome/131"})
        if "google.com" not in urlparse(r.url).netloc:
            return r.url
    except Exception:  # noqa: BLE001
        pass
    bc = (item.get("breadcrumb") or "").split(" ")[0]
    return bc if bc.startswith("http") and "…" not in bc and "..." not in bc else None


def serp(kw, loc, lang):
    r = first_result(post("serp/google/organic/live/advanced",
                          [{"keyword": kw, "location_code": loc, "language_code": lang,
                            "depth": 30, "device": "desktop"}]))
    items = r[0]["items"] if r else []
    features = sorted({i["type"] for i in items if i["type"] != "organic"})
    organic = [i for i in items if i["type"] == "organic"]
    # Since Nov 2026 DataForSEO returns Google's google.com/goto?url= click wrappers. Resolve them.
    wrapped = [i for i in organic if "google.com/goto" in (i.get("url") or "")]
    if wrapped:
        resolved = pmap(resolve_goto, wrapped, workers=6)
        for i, u in zip(wrapped, resolved):
            if u:
                i["url"], i["domain"] = u, urlparse(u).netloc
    rows = [{"position": i["rank_group"], "rank_absolute": i["rank_absolute"], "url": i["url"],
             "domain": i["domain"], "root": root(i["domain"]), "kind": kind_of(i["domain"]),
             "title": i.get("title"), "description": i.get("description"),
             "website_name": i.get("website_name"), "timestamp": i.get("timestamp")}
            for i in organic]
    aio = next((i for i in items if i["type"] == "ai_overview"), None)
    aio_refs = []
    if aio:
        for ref in aio.get("references") or []:
            aio_refs.append({"domain": ref.get("domain"), "url": ref.get("url")})
    return {"features": features, "organic": rows, "ai_overview_refs": aio_refs,
            "se_results_count": r[0].get("se_results_count") if r else None,
            "check_url": r[0].get("check_url") if r else None}


def target_page_from_labs(site, kw, loc, lang):
    r = first_result(post("dataforseo_labs/google/ranked_keywords/live",
                          [{"target": site, "location_code": loc, "language_code": lang, "limit": 1,
                            "filters": [["keyword_data.keyword", "=", kw]]}]))
    items = (r[0].get("items") or []) if r else []
    if not items:
        return None, None
    s = items[0]["ranked_serp_element"]["serp_item"]
    return s.get("url"), s.get("rank_group")


def page_links(urls):
    r = first_result(post("backlinks/bulk_pages_summary/live", [{"targets": urls}]))
    out = {}
    for it in (r[0].get("items") or []) if r else []:
        out[it["url"]] = {"referring_domains": it.get("referring_domains"),
                          "referring_main_domains": it.get("referring_main_domains"),
                          "backlinks": it.get("backlinks"), "page_rank": it.get("rank"),
                          "first_seen": it.get("first_seen")}
    return out


def domain_ranks(domains):
    r = first_result(post("backlinks/bulk_ranks/live", [{"targets": domains}]))
    return {it["target"]: it.get("rank") for it in ((r[0].get("items") or []) if r else [])}


def domain_refdomains(domains):
    r = first_result(post("backlinks/bulk_referring_domains/live", [{"targets": domains}]))
    return {it["target"]: it.get("referring_domains") for it in ((r[0].get("items") or []) if r else [])}


def traffic(targets, loc, lang):
    r = first_result(post("dataforseo_labs/google/bulk_traffic_estimation/live",
                          [{"targets": targets, "location_code": loc, "language_code": lang,
                            "item_types": ["organic"]}]))
    out = {}
    for it in (r[0].get("items") or []) if r else []:
        o = (it.get("metrics") or {}).get("organic") or {}
        out[it["target"]] = {"etv": o.get("etv"), "keywords": o.get("count")}
    return out


def anchors(url, terms):
    r = first_result(post("backlinks/anchors/live",
                          [{"target": url, "limit": 100, "order_by": ["referring_domains,desc"]}]))
    items = (r[0].get("items") or []) if r else []
    total = sum(i.get("referring_domains") or 0 for i in items)
    match = sum(i.get("referring_domains") or 0 for i in items
                if any(t in (i.get("anchor") or "").lower() for t in terms))
    top = [{"anchor": i.get("anchor"), "rd": i.get("referring_domains")} for i in items[:8]]
    return {"anchor_rd_total": total, "anchor_rd_query_match": match,
            "anchor_match_share": round(match / total, 3) if total else None, "top_anchors": top}


def content(url, terms):
    try:
        r = first_result(post("on_page/content_parsing/live", [{"url": url}]))
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:200]}
    it = (r[0].get("items") or [None])[0] if r else None
    if not it or not it.get("page_content"):
        return {"error": "not parsed", "status_code": (it or {}).get("status_code")}
    pc = it["page_content"]
    heads, words, body = [], 0, []
    for m in pc.get("main_topic") or []:
        if m.get("h_title"):
            heads.append({"level": m.get("level"), "text": " ".join(m["h_title"].split())})
        txt = " ".join(x.get("text") or "" for x in (m.get("primary_content") or []))
        body.append(txt)
        words += len(txt.split())
    h1 = next((h["text"] for h in heads if h["level"] == 1), heads[0]["text"] if heads else "")
    head_text = " ".join(h["text"].lower() for h in heads)
    body_text = " ".join(body).lower()
    tok = re.findall(r"[a-z0-9]+", body_text)
    return {"h1": h1, "headings": heads[:60], "word_count": words,
            "h1_terms": sum(t in h1.lower() for t in terms) / len(terms) if terms else None,
            "headings_with_term": sum(any(t in h["text"].lower() for t in terms) for h in heads),
            "heading_count": len(heads),
            "body_term_mentions": sum(tok.count(t) for t in terms),
            "head_text": head_text, "body_text": " ".join(tok)[:60000],
            "has_comments": bool(pc.get("comments")), "has_ratings": bool(pc.get("ratings"))}


def lighthouse(url):
    try:
        r = first_result(post("on_page/lighthouse/live/json",
                              [{"url": url, "for_mobile": True}], timeout=240))
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:200]}
    if not r:
        return {"error": "no result"}
    res = r[0]
    cats, aud = res.get("categories") or {}, res.get("audits") or {}

    def sc(k):
        v = (cats.get(k) or {}).get("score")
        return round(v * 100) if isinstance(v, (int, float)) else None

    def num(k):
        return (aud.get(k) or {}).get("numericValue")
    return {"performance": sc("performance"), "seo": sc("seo"),
            "lcp_ms": num("largest-contentful-paint"), "cls": num("cumulative-layout-shift"),
            "tbt_ms": num("total-blocking-time")}


def history(kw, loc, lang):
    r = first_result(post("dataforseo_labs/google/historical_serps/live",
                          [{"keyword": kw, "location_code": loc, "language_code": lang}]))
    snaps = []
    for s in sorted((r[0].get("items") or []) if r else [], key=lambda x: x["datetime"]):
        org = [i for i in s.get("items") or [] if i["type"] == "organic"]
        snaps.append({"date": s["datetime"][:10],
                      "features": s.get("item_types") or [],
                      "top": [{"position": i["rank_group"], "domain": i.get("domain"), "url": i.get("url")}
                              for i in org if i["rank_group"] <= 20]})
    return snaps


def whois(roots):
    r = first_result(post("domain_analytics/whois/overview/live",
                          [{"filters": [["domain", "in", roots]], "limit": len(roots)}]))
    return {it["domain"]: (it.get("created_datetime") or "")[:10] or None
            for it in ((r[0].get("items") or []) if r else [])}


def brand_volume(names, loc, lang):
    names = sorted({n for n in names if n})
    if not names:
        return {}
    r = first_result(post("keywords_data/google_ads/search_volume/live",
                          [{"keywords": names, "location_code": loc, "language_code": lang}]))
    return {it["keyword"]: it.get("search_volume") for it in r}


def cluster_depth(dom, terms, loc, lang):
    """How many keywords containing every query term the domain ranks for (topical focus proxy)."""
    flt = []
    for t in terms:
        if flt:
            flt.append("and")
        flt.append(["keyword_data.keyword", "like", f"%{t}%"])
    if len(flt) == 1:
        flt = flt[0]
    try:
        r = first_result(post("dataforseo_labs/google/ranked_keywords/live",
                              [{"target": dom, "location_code": loc, "language_code": lang,
                                "limit": 1, "filters": flt}]))
    except Exception:  # noqa: BLE001
        return None
    return (r[0].get("total_count") or 0) if r else 0


def video_meta(url):
    try:
        out = subprocess.run(["yt-dlp", "--skip-download", "--dump-json", "--no-warnings", url],
                             capture_output=True, text=True, timeout=90).stdout
        d = json.loads(out)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:120]}
    up = d.get("upload_date")
    return {"channel": d.get("channel"), "title": d.get("title"), "views": d.get("view_count"),
            "likes": d.get("like_count"), "comments": d.get("comment_count"),
            "subscribers": d.get("channel_follower_count"), "duration_s": d.get("duration"),
            "upload_date": f"{up[:4]}-{up[4:6]}-{up[6:]}" if up else None,
            "has_chapters": bool(d.get("chapters"))}


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keyword", required=True)
    ap.add_argument("--site", help="your domain, e.g. airankingskool.com")
    ap.add_argument("--page", help="your page for this keyword (auto-detected if omitted)")
    ap.add_argument("--location", type=int, default=2840)
    ap.add_argument("--language", default="en")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out")
    a = ap.parse_args()

    kw, loc, lang = a.keyword, a.location, a.language
    terms = query_terms(kw)
    out_dir = a.out or os.path.join(os.getcwd(), "rea-seo", slugify(kw))
    os.makedirs(out_dir, exist_ok=True)

    print(f"[1/9] SERP: {kw}")
    s = serp(kw, loc, lang)
    top = [r for r in s["organic"] if r["position"] <= a.top]

    target = None
    if a.site:
        site = root(a.site)
        live = next((r for r in s["organic"] if r["root"] == site), None)
        page, labs_pos = (live["url"], None) if live else (a.page, None)
        if not page:
            page, labs_pos = target_page_from_labs(site, kw, loc, lang)
        if page:
            target = {"url": page, "domain": urlparse(page).netloc, "root": site, "kind": kind_of(site),
                      "live_position": live["position"] if live else None, "labs_position": labs_pos,
                      "title": live["title"] if live else None, "in_top": bool(live and live["position"] <= a.top)}

    rows = list(top)
    if target and not target["in_top"]:
        rows.append({**target, "position": target["live_position"], "is_target": True})
    for r in rows:
        r["is_target"] = bool(target and r["url"].rstrip("/") == target["url"].rstrip("/"))
    web = [r for r in rows if r["kind"] == "web"]
    web_urls = [r["url"] for r in web]
    roots_web = sorted({r["root"] for r in web})

    print(f"[2/9] page links ({len(web_urls)} pages)")
    pl = page_links(web_urls) if web_urls else {}
    print("[3/9] domain authority")
    dr = domain_ranks(roots_web) if roots_web else {}
    drd = domain_refdomains(roots_web) if roots_web else {}
    print("[4/9] traffic (domains + pages)")
    tr = traffic(roots_web + web_urls, loc, lang) if web_urls else {}
    print("[5/9] anchors")
    linked = [u for u in web_urls if (pl.get(u) or {}).get("referring_domains")]
    an = dict(zip(linked, pmap(lambda u: anchors(u, terms), linked)))
    print("[6/9] content parsing")
    ct = dict(zip(web_urls, pmap(lambda u: content(u, terms), web_urls)))
    print("[7/9] lighthouse (mobile)")
    lh = dict(zip(web_urls, pmap(lighthouse, web_urls, workers=10)))
    print("[8/9] history, whois, brand demand, topical depth")
    hist = history(kw, loc, lang)
    who = whois(roots_web) if roots_web else {}
    brands = {r["root"]: brand_of(r) for r in web}
    bv = brand_volume(list(brands.values()), loc, lang)
    depth = dict(zip(roots_web, pmap(lambda d: cluster_depth(d, terms, loc, lang), roots_web)))
    print("[9/9] video results")
    vids = [r for r in rows if r["kind"] == "video"]
    vm = dict(zip([v["url"] for v in vids], pmap(video_meta, [v["url"] for v in vids], workers=4)))

    for r in rows:
        u, d = r["url"], r["root"]
        if r["kind"] == "web":
            r["links"] = pl.get(u) or {}
            r["anchors"] = an.get(u) or {}
            r["content"] = ct.get(u) or {}
            r["lighthouse"] = lh.get(u) or {}
            r["page_traffic"] = tr.get(u) or {}
            r["site"] = {"domain_rank": dr.get(d), "referring_domains": drd.get(d),
                         "traffic": tr.get(d) or {}, "created": who.get(d),
                         "brand": brands.get(d), "brand_volume": bv.get(brands.get(d)),
                         "cluster_depth": depth.get(d)}
        elif r["kind"] == "video":
            r["video"] = vm.get(u) or {}

    data = {"keyword": kw, "terms": terms, "location_code": loc, "language_code": lang,
            "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "serp": {k: v for k, v in s.items() if k != "organic"},
            "serp_beyond_top": [{"position": r["position"], "domain": r["domain"], "url": r["url"]}
                                for r in s["organic"] if r["position"] > a.top],
            "results": rows, "target": target, "history": hist,
            "cost": {"total_usd": round(COST["total"], 4), "calls": len(COST["calls"]),
                     "by_endpoint": _by_endpoint()}}
    path = os.path.join(out_dir, "collected.json")
    json.dump(data, open(path, "w"), indent=1)
    print(f"done -> {path}  cost ${COST['total']:.3f} over {len(COST['calls'])} calls")


def _by_endpoint():
    agg = {}
    for c in COST["calls"]:
        agg[c["endpoint"]] = round(agg.get(c["endpoint"], 0) + c["cost"], 4)
    return agg


if __name__ == "__main__":
    main()
