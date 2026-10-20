"""Makes the app's page at https://mass-outreach.com readable without JavaScript.

Streamlit's built-in page is an empty shell titled "Streamlit" that says
"You need to enable JavaScript to run this app." Google's verification checker
reads that raw page, so it saw no app name, no description, and no privacy link.

This script edits Streamlit's index.html so the raw page has:
  - the title "Mass Outreach"
  - a description of what the app does and why it asks for Google access
  - links to the Privacy Policy and Terms of Service
The text sits inside <div id="root">, so people with JavaScript only see it for a
moment while the app loads; the app then replaces it.

Runs on Render as part of the Build Command, and app.py also runs it at startup as
a backup. Safe to run any number of times.
"""

import os
import re

import streamlit

APP_NAME = "Mass Outreach"
HOME = "https://www.mass-outreach.com"
PRIVACY = "https://www.mass-outreach.com/privacy"
TERMS = "https://www.mass-outreach.com/terms"
CONTACT = "leokarpel98@gmail.com"

TITLE = f"{APP_NAME}: personal job outreach from your own Gmail"
DESCRIPTION = (f"{APP_NAME} helps job seekers email hiring managers directly. Add a job, list the people, "
               "and send personalized emails from your own Gmail.")

START, END = "<!-- mass-outreach:start -->", "<!-- mass-outreach:end -->"

CONTENT = f"""{START}
<div style="max-width:720px;margin:40px auto;padding:0 20px;font:16px/1.6 system-ui,-apple-system,'Segoe UI',sans-serif;color:#16201C">
  <h1 style="font-size:2rem;margin:0 0 8px">{APP_NAME}</h1>
  <p style="font-size:1.1rem;margin:0 0 20px"><strong>{APP_NAME}</strong> is a web app for job seekers. Add a job posting,
  list the people on the hiring team, and send each person a personalized email from your own Gmail account.</p>

  <h2 style="font-size:1.25rem;margin:24px 0 8px">How it works</h2>
  <ol>
    <li>Sign in with Google.</li>
    <li>Enter the job link, company, and job title.</li>
    <li>Enter the company's email format and the names of the people to contact. The app builds each address.</li>
    <li>Write one message. Each person's name, the company, and the job title are filled in automatically.</li>
    <li>Preview every email, then click Send. Emails go out from your Gmail, so replies come to your inbox.</li>
  </ol>

  <h2 style="font-size:1.25rem;margin:24px 0 8px">Why {APP_NAME} asks for access to your Google account</h2>
  <ul>
    <li><strong>Your email address</strong>: to identify your account and confirm you're an approved user.</li>
    <li><strong>Send email on your behalf</strong>: to send only the emails you preview and approve, from your own address.</li>
  </ul>
  <p>{APP_NAME} cannot read, search, or delete your email, and it does not store the messages you send.
  Read the full <a href="{PRIVACY}">Privacy Policy</a>.</p>

  <h2 style="font-size:1.25rem;margin:24px 0 8px">Free version and approved users</h2>
  <p>Anyone can use the free version without signing in: each email opens in your own Gmail and you click Send.
  Approved users sign in so the app sends the whole list for them. Both are free. To get approved, email
  <a href="mailto:{CONTACT}">{CONTACT}</a>.</p>

  <p style="margin-top:28px"><a href="{HOME}">Home</a> &middot; <a href="{PRIVACY}">Privacy Policy</a> &middot;
  <a href="{TERMS}">Terms of Service</a> &middot; <a href="mailto:{CONTACT}">{CONTACT}</a></p>
  <p style="color:#56635D;font-size:0.9rem">Loading the app&hellip; If it doesn't load, turn on JavaScript in your browser.</p>
</div>
{END}"""


def index_path() -> str:
    return os.path.join(os.path.dirname(streamlit.__file__), "static", "index.html")


def patch(path: str | None = None) -> bool:
    """Returns True if the file was changed."""
    path = path or index_path()
    with open(path, encoding="utf-8") as f:
        html = f.read()
    original = html

    # Title and description
    html = re.sub(r"<title>.*?</title>", f"<title>{TITLE}</title>", html, count=1, flags=re.S)
    if 'name="description"' not in html:
        html = html.replace("</title>", f'</title>\n    <meta name="description" content="{DESCRIPTION}" />', 1)

    # Readable content inside #root (replaced by the app once it loads)
    if START in html:
        html = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: CONTENT, html, count=1, flags=re.S)
    else:
        html = re.sub(r'<div id="root">\s*</div>', lambda _: f'<div id="root">{CONTENT}</div>', html, count=1)

    # Friendlier no-JavaScript message
    html = re.sub(r"<noscript>.*?</noscript>",
                  f'<noscript>Turn on JavaScript to use {APP_NAME}. About the app: {HOME}</noscript>',
                  html, count=1, flags=re.S)

    if html != original:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return True
    return False


if __name__ == "__main__":
    p = index_path()
    print(("patched " if patch(p) else "already patched ") + p)
