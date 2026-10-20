"""Regenerates site/privacy.html and site/terms.html from the text in legal.py,
so the website and the app always show the same policy.

Run: uv run python build_site.py. This creates local artifacts only.
"""

import re
from pathlib import Path

import markdown

import legal

SITE = Path(__file__).parent / "site"

SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Mass Outreach</title>
<meta name="description" content="{description}">
<style>
body {{font: 1rem/1.6 system-ui, sans-serif; max-width: 850px; margin: 2rem auto; padding: 1rem;}}
nav a, footer a {{margin-right: 1rem;}}
.table-wrap {{overflow-x: auto;}}
</style>
</head>
<body>
<header class="site">
  <div class="wrap">
    <strong class="brand">Mass Outreach</strong>
    <nav class="site" aria-label="Main">
      <a href="{other_href}">{other_label}</a>
      <a class="btn small" href="https://mass-outreach.com">Open the app</a>
    </nav>
  </div>
</header>

<main class="wrap legal">
{body}
</main>

<footer class="site">
  <div class="wrap">
    <span>© 2026 Mass Outreach</span>
    <span><a href="privacy.html">Privacy Policy</a> · <a href="terms.html">Terms of Service</a> · <a href="https://mass-outreach.com">Open the app</a></span>
  </div>
</footer>
</body>
</html>
"""


def render(md_text: str) -> str:
    html = markdown.markdown(md_text.strip(), extensions=["tables"])
    # "*Last updated: ...*" -> styled date line
    html = re.sub(r"<p><em>(Last updated:[^<]*)</em></p>", r'<p class="updated">\1</p>', html)
    # Wrap tables so they scroll sideways on phones instead of widening the page
    html = html.replace("<table>", '<div class="table-wrap"><table>').replace(
        "</table>", "</table></div>"
    )
    return html


PAGES = [
    (
        "privacy.html",
        "Privacy Policy",
        legal.PRIVACY,
        "How Mass Outreach accesses, uses, stores, shares, protects, and deletes your information, "
        "for invite-only outreach.",
        "terms.html",
        "Terms",
    ),
    (
        "terms.html",
        "Terms of Service",
        legal.TERMS,
        "Draft terms for invite-only outreach, approval, submission limits, and acceptable use.",
        "privacy.html",
        "Privacy",
    ),
]

if __name__ == "__main__":
    SITE.mkdir(parents=True, exist_ok=True)
    for filename, title, text, desc, other_href, other_label in PAGES:
        out = SHELL.format(
            title=title,
            description=desc,
            body=render(text),
            other_href=other_href,
            other_label=other_label,
        )
        (SITE / filename).write_text(out, encoding="utf-8")
        print("wrote", SITE / filename)
