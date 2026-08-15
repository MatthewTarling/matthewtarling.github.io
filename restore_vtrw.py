#!/usr/bin/env python3
"""
restore_vtrw.py
Strips matthewtarling.github.io down to the "Viewing the Rock World" project.

Run this from inside your local clone of the repo:
    python3 restore_vtrw.py

It only touches files in the current folder. Nothing is committed or pushed --
review with `git status` and `git diff` afterwards, and `git checkout .` undoes
everything if you don't like the result.
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# .change to ubc email ----
EMAIL = "matthew.tarling@ubc.ca"
# ---------------------------------------------------------------------------

ROOT = Path.cwd()

# Top-level folders and files to remove entirely.
DELETE = [
    "3d-printing", "3d-printing-old", "admin", "authors", "categories",
    "category", "event", "field-safety", "gallery", "post", "project",
    "publication", "publication-type", "publication_types", "slides",
    "tag", "tags", "talk", "teaching", "twit",
    "index.xml", "_headers", "_redirects", ".DS_Store",
]

# Leftover Wowchemy demo pages sitting inside outreach/ (Dynare tutorial theme).
DEMO_PAGES = ["best-practices", "deterministic", "estimation", "identification",
              "involvement"]

# Downloads that must survive in uploads/. Everything else there goes,
# including resume.pdf (your out-of-date CV).
KEEP_UPLOADS = {
    "slideviewerSTL.zip",     # the thin section viewer, linked from the project
    "12slidebox.zip",         # thin section boxes, linked from /printing/
    "24slidebox.zip",
    "frictionfitTSbox.zip",
}

# Navbar entries whose target no longer exists -> remove the whole <li>.
DEAD_NAV = {"/#about", "/#projects", "/teaching", "/#publications",
            "/field-safety", "/uploads/resume.pdf"}

log = []


def note(msg):
    log.append(msg)
    print(msg)


def sanity_check():
    if not (ROOT / "outreach" / "index.html").exists():
        sys.exit("ERROR: no outreach/index.html here. Run this from the root of "
                 "your matthewtarling.github.io clone.")
    if not (ROOT / ".git").exists():
        sys.exit("ERROR: this isn't a git repo. Run this inside your clone so "
                 "the changes are reversible.")


def remove(path: Path):
    if path.is_dir():
        shutil.rmtree(path)
        note(f"  removed folder  {path.relative_to(ROOT)}/")
    elif path.exists():
        path.unlink()
        note(f"  removed file    {path.relative_to(ROOT)}")


def step_delete_sections():
    note("\n[1] Removing the sections you no longer want online")
    for name in DELETE:
        remove(ROOT / name)


def step_clean_outreach():
    note("\n[2] Removing leftover Wowchemy demo pages from outreach/")
    for name in DEMO_PAGES:
        remove(ROOT / "outreach" / name)
    for f in (ROOT / "outreach").glob("dynare-tutorials*"):
        remove(f)


def step_prune_uploads():
    note("\n[3] Pruning uploads/ down to the project downloads")
    up = ROOT / "uploads"
    if not up.exists():
        return
    for f in up.iterdir():
        if f.name not in KEEP_UPLOADS:
            remove(f)
    for name in sorted(KEEP_UPLOADS):
        if (up / name).exists():
            note(f"  kept            uploads/{name}")


def strip_nav(html: str) -> str:
    """Delete dead navbar items and repoint Contact at an email address."""
    def drop(match):
        block = match.group(0)
        href = re.search(r'href="([^"]*)"', block)
        return "" if href and href.group(1) in DEAD_NAV else block

    html = re.sub(r'<li class="nav-item">.*?</li>', drop, html, flags=re.S)
    html = html.replace('href="/#contact"', f'href="mailto:{EMAIL}"')
    return html


def step_rewrite_pages():
    note("\n[4] Fixing navigation links on every remaining page")
    pages = sorted(ROOT.glob("**/index.html")) + [ROOT / "404.html"]
    changed = 0
    for page in pages:
        if not page.exists() or ".git" in page.parts or page == ROOT / "index.html":
            continue
        original = page.read_text(encoding="utf-8", errors="ignore")
        updated = strip_nav(original)
        # The landing page body links to the old homepage contact anchor.
        updated = updated.replace(
            "https://matthewtarling.github.io/#contact", f"mailto:{EMAIL}")
        if updated != original:
            page.write_text(updated, encoding="utf-8")
            changed += 1
    note(f"  updated {changed} pages (nav now: 3D Printing / Outreach / Contact)")


def step_redirect_homepage():
    note("\n[5] Turning the homepage into a redirect to /outreach/")
    (ROOT / "index.html").write_text(
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '  <meta charset="utf-8">\n'
        '  <title>Viewing the Rock World | Dr Matthew Tarling</title>\n'
        '  <link rel="canonical" href="https://matthewtarling.github.io/outreach/">\n'
        '  <meta http-equiv="refresh" content="0; url=/outreach/">\n'
        '  <meta name="description" content="Viewing the Rock World: a 3D-printed '
        'thin section viewer anyone can make for under $5.">\n'
        '</head>\n'
        '<body>\n'
        '  <p>Redirecting to the <a href="/outreach/">Viewing the Rock World</a> '
        'project&hellip;</p>\n'
        '  <script>window.location.replace("/outreach/");</script>\n'
        '</body>\n'
        '</html>\n', encoding="utf-8")
    note("  wrote index.html")


def step_nojekyll():
    note("\n[6] Adding .nojekyll so GitHub serves the files untouched")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    note("  wrote .nojekyll")


def step_search_index():
    note("\n[7] Rebuilding the site search index")
    f = ROOT / "index.json"
    if not f.exists():
        return
    try:
        records = json.load(f.open(encoding="utf-8"))
    except Exception:
        note("  could not parse index.json, leaving it alone")
        return
    kept = [r for r in records
            if str(r.get("relpermalink", "")).startswith(("/outreach/", "/printing/"))
            and not any(f"/{d}/" in str(r.get("relpermalink", "")) for d in DEMO_PAGES)]
    json.dump(kept, f.open("w", encoding="utf-8"), ensure_ascii=False)
    note(f"  index.json: {len(records)} entries -> {len(kept)}")


def step_sitemap():
    note("\n[8] Rebuilding sitemap.xml")
    urls = ["https://matthewtarling.github.io/outreach/",
            "https://matthewtarling.github.io/printing/"]
    for d in sorted((ROOT / "outreach").iterdir()):
        if d.is_dir() and (d / "index.html").exists():
            urls.append(f"https://matthewtarling.github.io/outreach/{d.name}/")
    body = "\n".join(f"  <url><loc>{u}</loc></url>" for u in sorted(urls))
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n", encoding="utf-8")
    note(f"  sitemap.xml: {len(urls)} pages")


def step_404():
    note("\n[9] Replacing the 404 page (it listed the deleted sections)")
    (ROOT / "404.html").write_text(
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '  <title>Page not found | Dr Matthew Tarling</title>\n'
        '  <style>\n'
        '    body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;\n'
        '         max-width:34rem;margin:18vh auto;padding:0 1.5rem;line-height:1.6;\n'
        '         color:#222}\n'
        '    a{color:#0b6}\n'
        '  </style>\n'
        '</head>\n'
        '<body>\n'
        '  <h1>Page not found</h1>\n'
        '  <p>This part of the old site is no longer online. The\n'
        '     <a href="/outreach/">Viewing the Rock World</a> project is still here.</p>\n'
        f'  <p>Questions? <a href="mailto:{EMAIL}">{EMAIL}</a></p>\n'
        '</body>\n'
        '</html>\n', encoding="utf-8")
    note("  wrote 404.html")


def main():
    sanity_check()
    before = sum(f.stat().st_size for f in ROOT.rglob("*")
                 if f.is_file() and ".git" not in f.parts)
    step_delete_sections()
    step_clean_outreach()
    step_prune_uploads()
    step_rewrite_pages()
    step_redirect_homepage()
    step_nojekyll()
    step_search_index()
    step_sitemap()
    step_404()
    after = sum(f.stat().st_size for f in ROOT.rglob("*")
                if f.is_file() and ".git" not in f.parts)
    note(f"\nDone. Site went from {before/1e6:.0f} MB to {after/1e6:.0f} MB.")
    note("\nNow run:  git status        (see what changed)")
    note("          git add -A")
    note('          git commit -m "Trim site to Viewing the Rock World project"')
    note("          git push")


if __name__ == "__main__":
    main()
