"""REA SEO step 0: check this computer can run a teardown. Free, no API keys.

Usage: python3 check_setup.py
DataForSEO data comes from the DataForSEO MCP connector, which Claude checks separately.
"""
import importlib.util, os, sys

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
    import requests
    try:
        requests.get("https://www.google.com/robots.txt", timeout=15)
        line(True, "Internet access for live page checks")
    except Exception as e:  # noqa: BLE001
        line(False, "Internet access for live page checks", f"Could not reach the web ({str(e)[:80]})")
print("INFO DataForSEO: uses the DataForSEO MCP connector (no API login needed here)")
sys.exit(0 if ok else 1)
