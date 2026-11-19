"""REA SEO step 5: resolve the live SERP, guess page types, print the MCP calls to make. Free.

Usage: python3 prepare.py rea-seo/<slug>
Reads  run.json, rivals.json, serp.json     Writes targets.json + an mcp.json skeleton to fill in.
"""
import os, sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import UA, root_of_url, kind_of, guess_page_type, load, save  # noqa: E402


def resolve(item):
    """Google wraps result URLs in google.com/goto. Follow it; fall back to the breadcrumb."""
    url = item.get("url") or ""
    if url and "google." not in urlparse(url).netloc:
        return url
    try:
        r = requests.get(url, allow_redirects=True, timeout=20, headers={"User-Agent": UA})
        if "google." not in urlparse(r.url).netloc:
            return r.url
    except Exception:  # noqa: BLE001
        pass
    bc = (item.get("breadcrumb") or "").split(" ")[0]
    return bc if bc.startswith("http") and "…" not in bc and "..." not in bc else None


def main(run):
    cfg, rv, serp = load(f"{run}/run.json"), load(f"{run}/rivals.json"), load(f"{run}/serp.json")
    if not (cfg and rv and serp):
        sys.exit("Missing run.json, rivals.json or serp.json in " + run)
    org = sorted(serp.get("organic") or [], key=lambda x: x.get("position") or 99)
    with ThreadPoolExecutor(8) as ex:
        urls = list(ex.map(resolve, org))
    rows = []
    for it, u in zip(org, urls):
        if not u:
            print(f"  could not resolve #{it.get('position')}: {it.get('title')}")
            continue
        r = root_of_url(u)
        rows.append({"position": it.get("position"), "url": u, "root": r, "kind": kind_of(r),
                     "title": it.get("title"), "website_name": it.get("website_name")})

    pidx = [k["keyword"] for k in cfg["keywords"]].index(cfg["primary"])
    pages = serp.get("site_pages") or {}
    brands = serp.get("brands") or {}
    sites = []
    for role, r, labs in [("you", cfg["site"], rv["you"]["positions"])] + \
                         [("rival", x["root"], x["positions"]) for x in rv["rivals"]]:
        live = next((x for x in rows if x["root"] == r), None)
        pg = pages.get(r) or {}
        url = pg.get("url") or (live or {}).get("url") or f"https://{r}/"
        sites.append({"role": role, "root": r, "url": url,
                      "brand": cfg["brand"] if role == "you" else brands.get(r) or r.split(".")[0],
                      "position": pg.get("position") or labs[pidx],
                      "live_position": (live or {}).get("position")})

    save(f"{run}/targets.json", {"primary": cfg["primary"], "rows": rows, "sites": sites})
    types = {x["url"]: guess_page_type(x["url"], x["kind"], x["title"]) for x in rows}
    types.update({s["url"]: guess_page_type(s["url"], "web") for s in sites if s["url"] not in types})
    mcp_path = f"{run}/mcp.json"
    if not os.path.exists(mcp_path):
        blank = lambda: {"rank": None, "referring_domains": None, "referring_domains_nofollow": None,  # noqa: E731
                         "spam_score": None, "etv": None, "page_referring_domains": None,
                         "performance": None, "lcp_ms": None, "cls": None, "llm_mentions": None,
                         "created": None, "brand_volume": None,
                         "gbp": {"name": None, "city": None, "category": None, "extra_categories": None,
                                 "rating": None, "reviews": None, "photos": None, "services": None,
                                 "claimed": None}}
        save(mcp_path, {"page_types": types, "sites": {s["root"]: blank() for s in sites},
                        "link_gap": {"total": None, "items": []},
                        "chatgpt": {"sources": [], "mentioned": {s["root"]: None for s in sites}},
                        "calls": 0})

    roots = [s["root"] for s in sites]
    purls = [s["url"] for s in sites]
    rivals = roots[1:]
    L = cfg["location_name"]
    print("\nPages compared:")
    for s in sites:
        print(f'  {s["role"]:5} #{s["position"] or "-":<3} {s["url"]}')
    print("\nPage-one page types (first guess, fix them in mcp.json page_types):")
    for x in rows:
        print(f'  #{x["position"]:<2} {types[x["url"]]:18} {x["root"]:30} {(x["title"] or "")[:50]}')
    print(f"""
Now make these DataForSEO MCP calls and fill {mcp_path}  (sites[<root>].<field>):

 1 backlinks_bulk_ranks              targets={roots}  -> rank
 2 backlinks_bulk_referring_domains  targets={roots}  -> referring_domains, referring_domains_nofollow
 3 backlinks_bulk_spam_score         targets={roots}  -> spam_score
 4 backlinks_bulk_pages_summary      targets={purls}
     -> page_referring_domains (missing field = 0)
 5 dataforseo_labs_bulk_traffic_estimation targets={roots} location_name="{L}"  -> etv
 6 on_page_lighthouse                once per page above  -> performance (score x 100), lcp_ms, cls
 7 domain_analytics_whois_overview   filters=["domain","in",{roots}] limit={len(roots)}  -> created (YYYY-MM-DD)
 8 kw_data_google_ads_search_volume  keywords={[s["brand"].lower() for s in sites]} location_name="{L}"  -> brand_volume
 9 ai_opt_llm_ment_agg_metrics       target=[{{"domain":"<root>"}}] platform="google" location_name="{L}", once per site
     -> llm_mentions (total.platform[0].mentions, 0 if no items)
10 business_data_business_listings_search filters=["domain","in",{roots}] limit=8
     -> gbp: per site, the listing with the most reviews (name, city, category, extra_categories count,
        rating, reviews, photos = total_photos, services count, claimed). If a main listing is missing,
        search again with title="<business name>".
11 backlinks_domain_intersection     targets={rivals} exclude_targets=["{roots[0]}"] limit=15
     -> link_gap.total = total_count; items [{{domain, rank, spam}}] = sites linking to ALL rivals, not you
12 ai_optimization_chat_gpt_scraper  keyword="{cfg['primary']}" force_web_search=true
     -> chatgpt.sources (cited domains), chatgpt.mentioned[root] (brand or domain named in the answer)

Set "calls" to the total MCP calls made in this run. Leave null where a call fails.
Then: python3 teardown.py {run}""")


if __name__ == "__main__":
    main(sys.argv[1].rstrip("/\\"))
