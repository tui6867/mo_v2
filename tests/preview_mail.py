"""Anonymous UI-only preview. Synthetic key; no usable sign-in or SMTP credentials.

Build frontend first, then run `uv run python -m tests.preview_mail`.
Never use this HTTP-only preview for app-password entry or real sign-in.
"""

import uvicorn
from fastapi.staticfiles import StaticFiles

from outreach.api.app import create_app
from outreach.api.config import Settings

if __name__ == "__main__":
    settings = Settings(
        "https://gnmimpoeqxeczjhvzrrx.supabase.co",
        "synthetic-not-a-valid-key",
        "https://localhost:8443",
        "synthetic-preview-only-" + "s" * 64,
        "test-recipient@example.com",
    )
    app = create_app(settings)
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="preview")
    uvicorn.run(app, host="127.0.0.1", port=8513, access_log=False)
