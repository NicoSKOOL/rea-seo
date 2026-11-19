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
    found = list(dfs.candidates())
    line(bool(found), f"DataForSEO login found ({len(found)} saved)" if found else "DataForSEO login found",
         "Install the DataForSEO MCP in Claude Code with your API login (see README), "
         f'or copy "{os.path.join(skill, ".env.example")}" to ".env" and fill it in')
    if found:
        good = None
        for src, u, p in found:
            bal = dfs.check_login(u, p)
            if bal is not None:
                good = (src, bal)
                break
            print(f"WARN Rejected by DataForSEO: login from {src}")
        line(bool(good), f"DataForSEO login works (from {good[0]}), balance ${good[1]:.2f}" if good
             else "DataForSEO login works",
             "Every saved login was rejected. Get the current API login from app.dataforseo.com/api-access")
        if good and good[1] < 1.5:
            print("WARN Balance is under $1.50. One run costs about $0.95.")

print("INFO yt-dlp " + ("found" if shutil.which("yt-dlp") else "not found (optional: only adds YouTube video stats)"))
sys.exit(0 if ok else 1)
