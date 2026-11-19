"""Open a run's report in the default browser (Mac, Windows, Linux).

Usage: python3 scripts/open_report.py rea-seo/<slug>
Opens package/report.html when it exists (its file links work there), else report.html.
"""
import os, sys, webbrowser

run = sys.argv[1].rstrip("/\\")
for p in (os.path.join(run, "package", "report.html"), os.path.join(run, "report.html")):
    if os.path.exists(p):
        path = os.path.abspath(p)
        webbrowser.open("file://" + path.replace("\\", "/") if os.name != "nt" else path)
        print(path)
        break
else:
    sys.exit(f"No report.html in {run}")
