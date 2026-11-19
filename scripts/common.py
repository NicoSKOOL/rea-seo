"""Shared helpers for REA SEO (MCP edition). No API keys: DataForSEO data arrives via the MCP connector."""
import json, os, re
from urllib.parse import urlparse

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131 Safari/537.36 REA-SEO/2.0")

PLATFORMS = {"youtube.com": "video", "tiktok.com": "video", "reddit.com": "forum", "quora.com": "forum",
             "facebook.com": "platform", "instagram.com": "platform", "linkedin.com": "platform",
             "x.com": "platform", "twitter.com": "platform", "medium.com": "platform",
             "github.com": "platform", "wikipedia.org": "platform", "substack.com": "platform",
             "pinterest.com": "platform"}
# Big directories / aggregators. They rank, but they are not "the competitor" a business can copy.
DIRECTORIES = {"yelp.com", "zillow.com", "realtor.com", "redfin.com", "bbb.org", "yellowpages.com",
               "angi.com", "homeadvisor.com", "thumbtack.com", "tripadvisor.com", "nerdwallet.com",
               "bankrate.com", "forbes.com", "lendingtree.com", "trustpilot.com", "mapquest.com",
               "nextdoor.com", "houzz.com", "indeed.com", "glassdoor.com", "amazon.com", "ebay.com",
               "wheree.com", "allmortgagedetail.com", "expertise.com", "birdeye.com", "usnews.com",
               "wallethub.com", "yellowpages.net", "merchantcircle.com", "consumeraffairs.com",
               "investopedia.com", "cnet.com", "businessinsider.com", "money.com", "fool.com",
               "manta.com", "superpages.com", "foursquare.com", "clutch.co", "g2.com", "capterra.com",
               "apple.com", "google.com", "local-real-estate.com", "duciary.com", "morty.com"}
PAGE_TYPES = ["homepage", "location page", "service page", "directory listing", "list article",
              "article", "tool / rates", "forum / social", "video", "other"]
STOP = {"the", "a", "an", "for", "to", "of", "and", "in", "on", "with", "how", "what", "is",
        "best", "vs", "your", "my", "i", "you", "it", "by", "at", "or", "do", "does", "near", "me"}


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def root(domain):
    d = (domain or "").lower().split(":")[0]
    d = d.removeprefix("www.").removeprefix("m.")
    parts = d.split(".")
    if len(parts) > 2 and len(parts[-2]) <= 3 and len(parts[-1]) == 2:  # co.uk, com.au
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def root_of_url(url):
    return root(urlparse(url).netloc)


def kind_of(r):
    for k, v in PLATFORMS.items():
        if r == k or r.endswith("." + k):
            return v
    if r in DIRECTORIES:
        return "directory"
    if re.search(r"\.(gov|edu|mil)(\.[a-z]{2})?$", r):
        return "institution"
    return "web"


def guess_page_type(url, kind, title=""):
    """First guess only. Claude corrects it in mcp.json after looking at the titles."""
    path = urlparse(url).path.lower().rstrip("/")
    t = (title or "").lower()
    if kind == "video":
        return "video"
    if kind in ("forum", "platform"):
        return "forum / social"
    if re.match(r"(the )?(top|best) ?\d*", t) and kind != "web":
        return "list article" if re.search(r"/(blog|news|article)", path) else "directory listing"
    if kind == "directory":
        return "directory listing"
    if not path:
        return "homepage"
    if re.search(r"/(blog|news|articles?|guides?|learn|resources|insights)(/|$)", path):
        return "list article" if re.match(r"(the )?(top|best) ", t) else "article"
    if re.search(r"/(locations?|branch(es)?|areas?|cities|city|offices?|near-me)(/|$)", path):
        return "location page"
    if re.search(r"(calculator|rates?)(/|$|-)", path):
        return "tool / rates"
    return "service page"


def query_terms(q):
    return [t for t in re.findall(r"[a-z0-9]+", q.lower()) if t not in STOP]


def load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False, default=str)
