"""REA SEO, step 0: check this computer can run a teardown. Costs nothing.

Usage: python3 scripts/check_setup.py
Prints one line per check and exits 1 if anything blocks a run.
"""
import importlib.util, os, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ok = True


def line(good, msg, fix=""):
    global ok
    print(("OK   " if good else "FIX  ") + msg + ("" if good else f"\n     -> {fix}"))
    ok = ok and good


line(sys.version_info >= (3, 9), f"Python {sys.version.split()[0]}", "Install Python 3.9 or newer from python.org")
missing = [m for m in ("requests", "bs4") if importlib.util.find_spec(m) is None]
skill = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
line(not missing, "Python packages (requests, beautifulsoup4)",
     f'{sys.executable} -m pip install -r "{os.path.join(skill, "requirements.txt")}"')

if not missing:
    import dfs
    dfs._load_dotenv()
    have = bool(os.environ.get("DATAFORSEO_USERNAME") and os.environ.get("DATAFORSEO_PASSWORD"))
    line(have, "DataForSEO login found",
         f'Copy "{os.path.join(skill, ".env.example")}" to ".env" in the same folder and fill in the API login')
    if have:
        import requests
        try:
            r = requests.get(f"{dfs.BASE}/appendix/user_data", headers={"Authorization": dfs._auth()}, timeout=30)
            res = (r.json().get("tasks") or [{}])[0].get("result") or [{}]
            bal = (res[0].get("money") or {}).get("balance")
            good = r.status_code == 200 and bal is not None
            line(good, f"DataForSEO login works, balance ${bal:.2f}" if good else "DataForSEO login works",
                 "Login rejected. Use the API login from app.dataforseo.com/api-access")
            if good and bal < 1.5:
                print("WARN Balance is under $1.50. One run costs about $0.95.")
        except Exception as e:  # noqa: BLE001
            line(False, "DataForSEO reachable", f"Could not reach api.dataforseo.com ({str(e)[:80]})")

print("INFO yt-dlp " + ("found" if shutil.which("yt-dlp") else "not found (optional: only adds YouTube video stats)"))
sys.exit(0 if ok else 1)
