"""Tiny DataForSEO v3 client with a running cost ledger."""
import base64, os
import requests

BASE = "https://api.dataforseo.com/v3"
COST = {"total": 0.0, "calls": []}


def _load_dotenv():
    """Fill missing DATAFORSEO_* vars from a .env in the current folder or the skill folder."""
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(os.getcwd(), ".env"), os.path.join(here, "..", ".env")):
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.replace("export ", "").strip()
            if k.startswith("DATAFORSEO_") and not os.environ.get(k):
                os.environ[k] = v.strip().strip('"').strip("'")


def _auth():
    _load_dotenv()
    u, p = os.environ.get("DATAFORSEO_USERNAME"), os.environ.get("DATAFORSEO_PASSWORD")
    if not u or not p:
        raise SystemExit("DataForSEO login missing. Add DATAFORSEO_USERNAME and DATAFORSEO_PASSWORD "
                         "(API login from app.dataforseo.com/api-access) to a .env file in the skill "
                         "folder, then run again.")
    return "Basic " + base64.b64encode(f"{u}:{p}".encode()).decode()


def post(path, tasks, timeout=180):
    """POST a list of task dicts. Returns the list of task objects; records cost."""
    r = requests.post(f"{BASE}/{path}", json=tasks, timeout=timeout,
                      headers={"Authorization": _auth(), "Content-Type": "application/json"})
    if r.status_code != 200:
        raise RuntimeError(f"{path}: HTTP {r.status_code} {r.text[:300]}")
    data = r.json()
    cost = data.get("cost") or 0
    COST["total"] += cost
    COST["calls"].append({"endpoint": path, "cost": cost})
    return data.get("tasks") or []


def first_result(tasks):
    """Result list of the first task, or [] when the task errored."""
    if not tasks:
        return []
    t = tasks[0]
    if t.get("status_code") not in (20000,):
        return []
    return t.get("result") or []
