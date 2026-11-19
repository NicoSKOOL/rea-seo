"""REA SEO step 1: create the run folder. Free.

Usage:
  python3 start.py --site example.com --brand "Example Lending" \
      --kw "mortgage lender south carolina=260" --kw "fha lenders in south carolina=260" ... \
      [--location "United States"] [--serp-location "South Carolina,United States"] [--language en]

The FIRST --kw is the primary keyword (the one torn down in detail). 5 to 10 keywords in total.
"keyword=volume": monthly search volume is optional.
"""
import argparse, os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import slugify, root, save  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--site", required=True)
ap.add_argument("--brand", help='the business name, e.g. "Example Lending"')
ap.add_argument("--kw", action="append", required=True, help='"keyword=volume", repeat; first is primary')
ap.add_argument("--location", default="United States", help="country, for Labs and volume data")
ap.add_argument("--serp-location", help='live SERP location, e.g. "South Carolina,United States"')
ap.add_argument("--language", default="en")
a = ap.parse_args()

kws = []
for k in a.kw:
    name, _, vol = k.partition("=")
    kws.append({"keyword": name.strip().lower(), "volume": int(vol) if vol.strip().isdigit() else None})
site = root(a.site.replace("https://", "").replace("http://", "").split("/")[0])
run = os.path.join(os.getcwd(), "rea-seo", slugify(site))
os.makedirs(run, exist_ok=True)
save(os.path.join(run, "run.json"), {
    "site": site, "brand": (a.brand or site.split(".")[0]).strip(), "keywords": kws,
    "primary": kws[0]["keyword"], "location_name": a.location,
    "serp_location": a.serp_location or a.location, "language_code": a.language,
    "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
print(run)
print("\nNext: dataforseo_labs_google_serp_competitors with keywords=")
print([k["keyword"] for k in kws])
print(f'location_name="{a.location}", language_code="{a.language}", limit=30')
print(f"Then write {os.path.join(run, 'competitors.json')} (see SKILL.md) and run rivals.py.")
