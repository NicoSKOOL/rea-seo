"""Tiny DataForSEO v3 client with a running cost ledger."""
import base64, json, os
import requests

BASE = "https://api.dataforseo.com/v3"
COST = {"total": 0.0, "calls": []}


def _dotenv_creds():
    """DATAFORSEO_* pairs from a .env in the current folder or the skill folder."""
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(os.getcwd(), ".env"), os.path.join(here, "..", ".env")):
        if not os.path.exists(path):
            continue
        vals = {}
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k.replace("export ", "").strip()] = v.strip().strip('"').strip("'")
        yield f".env ({path})", vals.get("DATAFORSEO_USERNAME"), vals.get("DATAFORSEO_PASSWORD")


def _mcp_server_creds(name, cfg):
    """Login from one MCP server entry: env vars, or a Basic auth header (remote MCP)."""
    if "dataforseo" not in json.dumps(cfg).lower() and "dfs" not in name.lower():
        return None
    env = cfg.get("env") or {}
    if env.get("DATAFORSEO_USERNAME") and env.get("DATAFORSEO_PASSWORD"):
        return env["DATAFORSEO_USERNAME"], env["DATAFORSEO_PASSWORD"]
    auth = (cfg.get("headers") or {}).get("Authorization") or ""
    if auth.startswith("Basic "):
        try:
            u, p = base64.b64decode(auth[6:]).decode().split(":", 1)
            return u, p
        except Exception:  # noqa: BLE001
            return None
    return None


def _mcp_config_files():
    home = os.path.expanduser("~")
    files = [os.path.join(home, ".claude.json")]
    d = os.getcwd()
    while True:  # project .mcp.json in this folder or any parent
        files.append(os.path.join(d, ".mcp.json"))
        if os.path.dirname(d) == d:
            break
        d = os.path.dirname(d)
    files += [os.path.join(home, "Library", "Application Support", "Claude", "claude_desktop_config.json"),
              os.path.join(os.environ.get("APPDATA", ""), "Claude", "claude_desktop_config.json"),
              os.path.join(home, ".config", "Claude", "claude_desktop_config.json")]
    return files


def _mcp_creds():
    """DataForSEO logins saved in Claude Code / Claude desktop MCP configs (current project first)."""
    cwd = os.getcwd()
    for path in _mcp_config_files():
        try:
            data = json.load(open(path, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        projects = data.get("projects") or {}
        mine = sorted((k for k in projects if cwd.startswith(k)), key=len, reverse=True)
        others = [k for k in projects if k not in mine]
        # the project Claude is open in (and its parents), then user-wide servers, then other projects
        groups = [(k, projects[k].get("mcpServers") or {}) for k in mine]
        groups += [("", data.get("mcpServers") or {})]
        groups += [(k, projects[k].get("mcpServers") or {}) for k in others]
        for proj, servers in groups:
            for name, cfg in servers.items():
                c = _mcp_server_creds(name, cfg if isinstance(cfg, dict) else {})
                if c:
                    yield f"MCP '{name}' in {os.path.basename(path)}", c[0], c[1]


def candidates():
    """Every DataForSEO login this computer has, in priority order, without duplicates."""
    seen = set()
    srcs = [("environment variables", os.environ.get("DATAFORSEO_USERNAME"), os.environ.get("DATAFORSEO_PASSWORD"))]
    for src, u, p in [*srcs, *_dotenv_creds(), *_mcp_creds()]:
        if u and p and (u, p) not in seen:
            seen.add((u, p))
            yield src, u, p


def _header(u, p):
    return "Basic " + base64.b64encode(f"{u}:{p}".encode()).decode()


def check_login(u, p):
    """Free call. Returns the balance in USD, or None when the login is rejected."""
    try:
        r = requests.get(f"{BASE}/appendix/user_data", headers={"Authorization": _header(u, p)}, timeout=30)
        res = ((r.json().get("tasks") or [{}])[0].get("result") or [{}])[0]
        return (res.get("money") or {}).get("balance") if r.status_code == 200 else None
    except Exception:  # noqa: BLE001
        return None


_AUTH = {}


def find_login():
    """First saved login DataForSEO accepts: (source, balance, header). Exits with a clear message if none."""
    if "h" in _AUTH:
        return _AUTH["src"], _AUTH["bal"], _AUTH["h"]
    tried = []
    for src, u, p in candidates():
        bal = check_login(u, p)
        if bal is not None:
            _AUTH.update(src=src, bal=bal, h=_header(u, p))
            return src, bal, _AUTH["h"]
        tried.append(src)
    if tried:
        raise SystemExit("DataForSEO rejected every saved login (" + "; ".join(tried) + "). "
                         "Get the current API login from app.dataforseo.com/api-access.")
    raise SystemExit("No DataForSEO login found. Install the DataForSEO MCP in Claude Code with your API login, "
                     "or add DATAFORSEO_USERNAME and DATAFORSEO_PASSWORD to a .env file in the skill folder.")


def _auth():
    return find_login()[2]


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
