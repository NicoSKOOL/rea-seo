"""List the keywords in a saved dataforseo_labs_google_ranked_keywords result. Free.

Usage: python3 kwlist.py <saved-result-file> [--blog]
Prints: volume, position, keyword, ranking URL path. Blog/article URLs are hidden unless --blog.
Use it to pick the 5 to 10 commercial keywords for a run.
"""
import json, re, sys
from urllib.parse import urlparse

t = open(sys.argv[1], encoding="utf-8").read()
d = json.loads(t[t.find("{"):])
items = d.get("items") or (d.get("result") or [{}])[0].get("items") or []
show_blog = "--blog" in sys.argv
for it in items:
    k, s = it["keyword_data"], it["ranked_serp_element"]["serp_item"]
    path = urlparse(s.get("url") or "").path or "/"
    if not show_blog and re.search(r"/(blog|news|articles?|guides?|learn|resources)(/|$)", path):
        continue
    print(f'{k["keyword_info"].get("search_volume") or 0:>6}  #{s.get("rank_group"):<3} {k["keyword"]:<48} {path}')
